import asyncio
import logging
import random
import uuid
from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.config import settings
from app.models.story import Story, StoryStatus
from app.schemas.story import StoryCreateRequest
from app.services import audio_service, image_service, llm_service, storage_service

logger = logging.getLogger(__name__)

# Concurrency limits for external APIs to avoid 429 rate-limiting
IMAGE_SEMAPHORE = asyncio.Semaphore(2)
AUDIO_SEMAPHORE = asyncio.Semaphore(4)


async def _update_story(
    db: AsyncSession,
    story_id: uuid.UUID,
    **kwargs,
) -> None:
    """Helper: fetch story by id, apply kwargs updates, commit."""
    result = await db.execute(select(Story).where(Story.id == story_id))
    story: Story | None = result.scalar_one_or_none()
    if story is None:
        logger.error("Story %s not found during background update.", story_id)
        return
    for key, value in kwargs.items():
        setattr(story, key, value)
    story.updated_at = datetime.now(timezone.utc)
    from sqlalchemy.orm.attributes import flag_modified
    if "pages" in kwargs:
        flag_modified(story, "pages")
    await db.flush()
    await db.commit()


async def generate_story_background(
    story_id: str,
    request: StoryCreateRequest,
    db: AsyncSession,
) -> None:
    """
    Progressive story generation pipeline executed as a FastAPI BackgroundTask.

    1. Call LLM → Get (title, raw pages).
    2. Save all pages immediately as text-only (ready=False) with title.
    3. Generate audio for all pages & image for odd pages (1, 3, 5, 7) using semaphores.
       Even pages reuse the preceding odd page's image path.
    4. As each page completes, upload assets, update its ready=True, and commit to DB.
    5. Once all pages are ready, update story status to completed.
    """
    story_uuid = uuid.UUID(story_id)

    try:
        # ── Step 1: Mark as generating ────────────────────────────────────────
        logger.info("Story %s: starting progressive pipeline.", story_id)
        await _update_story(db, story_uuid, status=StoryStatus.generating)

        # ── Step 2: LLM — generate all page text/prompts & title ──────────────
        logger.info("Story %s: calling LLM for %d pages.", story_id, request.page_count)
        title, pages_raw = await llm_service.generate_story_pages(
            user_cues=request.user_cues,
            page_count=request.page_count,
        )

        total_pages = len(pages_raw)
        seed: int = random.randint(0, 2**31 - 1)
        logger.info("Story %s: LLM returned %d pages. Title: %r. Seed: %d", story_id, total_pages, title, seed)

        # Initialize the pages list in the DB with text and ready=False
        current_pages = []
        for p in pages_raw:
            current_pages.append({
                "page_number": p["page_number"],
                "text": p["text"],
                "audio_text": p["audio_text"],
                "image_prompt": p.get("image_prompt", ""),
                "ready": False,
                "image_path": None,
                "audio_path": None,
                "alignment": None,
            })

        await _update_story(
            db,
            story_uuid,
            title=title,
            pages=current_pages,
            page_count=total_pages,
        )

        # ── Step 3: Progressive Media Generation ──────────────────────────────
        # Odd pages (1, 3, 5, 7) generate a new image.
        # Even pages (2, 4, 6, 8) reuse the previous odd page's image.
        db_lock = asyncio.Lock()
        image_futures: dict[int, asyncio.Future] = {}

        for p in pages_raw:
            page_num = p["page_number"]
            if page_num % 2 == 1:
                image_futures[page_num] = asyncio.get_event_loop().create_future()

        async def _generate_and_upload_image(odd_page_num: int, prompt: str):
            async with IMAGE_SEMAPHORE:
                logger.info("Story %s: generating illustration for odd page %d", story_id, odd_page_num)
                img_bytes = await image_service.generate_image(prompt, seed)
                img_dest = f"stories/{story_id}/page_{odd_page_num}/image.png"
                await storage_service.upload_file(img_bytes, img_dest, "image/png")
                image_futures[odd_page_num].set_result(img_dest)
                return img_dest

        async def _process_single_page(idx: int):
            p = pages_raw[idx]
            page_num = p["page_number"]

            # 1. Image resolution
            if page_num % 2 == 1:
                # Odd page: generate its image
                img_path = await _generate_and_upload_image(page_num, p["image_prompt"])
            else:
                # Even page: wait for the previous odd page's image
                preceding_odd = page_num - 1
                logger.info("Story %s: page %d waiting to reuse image from page %d", story_id, page_num, preceding_odd)
                img_path = await image_futures[preceding_odd]

            # 2. Audio generation & upload
            async with AUDIO_SEMAPHORE:
                logger.info("Story %s: synthesizing narration for page %d", story_id, page_num)
                audio_bytes, alignment = await audio_service.generate_audio(
                    text=p["audio_text"],
                    voice_id=request.voice_id,
                )
                aud_dest = f"stories/{story_id}/page_{page_num}/audio.mp3"
                await storage_service.upload_file(audio_bytes, aud_dest, "audio/mpeg")

            # 3. Update DB atomically for this page
            async with db_lock:
                current_pages[idx]["ready"] = True
                current_pages[idx]["image_path"] = img_path
                current_pages[idx]["audio_path"] = aud_dest
                current_pages[idx]["alignment"] = alignment
                await _update_story(db, story_uuid, pages=current_pages)
                logger.info("Story %s: Page %d is now READY and saved to DB.", story_id, page_num)

        # Process Page 1 with highest priority, while scheduling remaining pages
        # Launch page 1 immediately
        logger.info("Story %s: kicking off page tasks.", story_id)
        tasks = [_process_single_page(i) for i in range(total_pages)]
        await asyncio.gather(*tasks)

        # ── Step 4: Finalize as completed ─────────────────────────────────────
        logger.info("Story %s: all %d pages are ready! Marking completed.", story_id, total_pages)
        await _update_story(db, story_uuid, status=StoryStatus.completed)
        logger.info("Story %s: ✅ Pipeline complete.", story_id)

    except Exception as exc:
        logger.exception("Story %s: ❌ Pipeline failed: %s", story_id, exc)
        try:
            await _update_story(
                db,
                story_uuid,
                status=StoryStatus.failed,
                error_message=str(exc),
            )
        except Exception as db_exc:
            logger.error("Story %s: failed to save error state: %s", story_id, db_exc)

