"""
Story CRUD router — /api/story
"""

import uuid
import logging
from typing import Annotated

from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.deps import CurrentUser, DbSession
from app.models.story import Story, StoryStatus
from app.schemas.story import (
    StoryCreateRequest,
    StoryResponse,
    StoryStatusResponse,
    StoryUpdateRequest,
)
from app.services.story_orchestrator import generate_story_background
from app.database import AsyncSessionLocal

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api", tags=["stories"])


from app.services import storage_service
from app.config import settings

def _story_to_response(story: Story) -> StoryResponse:
    """
    Convert a Story ORM object to a StoryResponse Pydantic model.
    Generates fresh signed URLs on-the-fly for every page so that links never expire.
    """
    pages_data = []
    ready_count = 0

    if story.pages:
        for p in story.pages:
            p_dict = dict(p)
            is_ready = p_dict.get("ready", False)

            # Check if image/audio paths or existing URLs exist
            image_path = p_dict.get("image_path")
            audio_path = p_dict.get("audio_path")

            # Fallback for older stories that only stored GCS signed URLs
            if not image_path and p_dict.get("image_url"):
                # If page is marked ready or has audio, it's ready
                is_ready = True
                image_path = f"stories/{story.id}/page_{p_dict.get('page_number')}/image.png"

            if not audio_path and p_dict.get("audio_url"):
                audio_path = f"stories/{story.id}/page_{p_dict.get('page_number')}/audio.mp3"

            # Generate fresh signed URL if path is available and page is ready
            image_url = None
            audio_url = None

            if image_path:
                try:
                    gcs_uri = f"gs://{settings.GCS_BUCKET_NAME}/{image_path}"
                    image_url = storage_service.get_signed_url(gcs_uri, expiry_hours=settings.SIGNED_URL_EXPIRY_HOURS)
                except Exception as e:
                    logger.warning("Could not sign image URL for story %s: %s", story.id, e)
                    image_url = p_dict.get("image_url")

            if audio_path:
                try:
                    gcs_uri = f"gs://{settings.GCS_BUCKET_NAME}/{audio_path}"
                    audio_url = storage_service.get_signed_url(gcs_uri, expiry_hours=settings.SIGNED_URL_EXPIRY_HOURS)
                except Exception as e:
                    logger.warning("Could not sign audio URL for story %s: %s", story.id, e)
                    audio_url = p_dict.get("audio_url")

            if is_ready or (image_url and audio_url):
                ready_count += 1
                is_ready = True

            p_dict["ready"] = is_ready
            p_dict["image_url"] = image_url
            p_dict["audio_url"] = audio_url
            pages_data.append(p_dict)

    return StoryResponse(
        id=str(story.id),
        user_id=story.user_id,
        status=story.status.value,
        title=story.title,
        page_count=story.page_count,
        pages_ready=ready_count,
        pages=pages_data if pages_data else None,
        created_at=story.created_at,
        updated_at=story.updated_at,
        error_message=story.error_message,
    )


# ── POST /api/story ────────────────────────────────────────────────────────────

@router.post(
    "/story",
    response_model=StoryStatusResponse,
    status_code=status.HTTP_202_ACCEPTED,
    summary="Create a new story generation job",
)
async def create_story(
    request: StoryCreateRequest,
    background_tasks: BackgroundTasks,
    current_user: CurrentUser,
    db: DbSession,
) -> StoryStatusResponse:
    """
    Validates the Firebase token, calculates page count based on duration_minutes,
    creates a Story DB record with ``status=pending``, then launches the full
    generation pipeline as a background task.
    """
    token_uid: str = current_user["uid"]
    if request.user_id != token_uid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="user_id in body does not match authenticated token uid.",
        )

    # 5 minutes ≈ 700 words ≈ 8 pages at ~85-90 words per page
    # If duration_minutes is specified, calculate page count:
    if request.duration_minutes:
        calculated_pages = max(3, min(24, round(request.duration_minutes * 1.6)))
        effective_page_count = calculated_pages
    else:
        effective_page_count = request.page_count or 8

    # Combine prompt with user_cues if provided
    cues = list(request.user_cues)
    if request.prompt and request.prompt.strip():
        cues.insert(0, request.prompt.strip())
    if not cues:
        cues = ["magical bedtime adventure"]

    story = Story(
        id=uuid.uuid4(),
        user_id=request.user_id,
        status=StoryStatus.pending,
        user_cues=cues,
        page_count=effective_page_count,
    )
    db.add(story)
    await db.flush()
    await db.commit()

    story_id_str = str(story.id)
    logger.info(
        "Created story %s for user %r (pages=%d, duration=%dmin). Launching background task.",
        story_id_str,
        request.user_id,
        effective_page_count,
        request.duration_minutes or 5,
    )

    # Update request object with effective fields for orchestrator
    request.page_count = effective_page_count
    request.user_cues = cues

    async def _bg_task() -> None:
        async with AsyncSessionLocal() as bg_db:
            await generate_story_background(
                story_id=story_id_str,
                request=request,
                db=bg_db,
            )

    background_tasks.add_task(_bg_task)

    return StoryStatusResponse(id=story_id_str, status="pending")


# ── GET /api/story/{story_id} ─────────────────────────────────────────────────

@router.get(
    "/story/{story_id}",
    response_model=StoryResponse,
    summary="Get a story by ID",
)
async def get_story(
    story_id: str,
    current_user: CurrentUser,
    db: DbSession,
) -> StoryResponse:
    """
    Returns the full story when ``status=completed`` (including signed URLs),
    or a lightweight status object when still pending/generating.
    """
    try:
        story_uuid = uuid.UUID(story_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid story_id format: {story_id!r}",
        )

    result = await db.execute(
        select(Story).where(
            Story.id == story_uuid,
            Story.deleted_at.is_(None),
        )
    )
    story: Story | None = result.scalar_one_or_none()

    if story is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found.")

    # Ownership check
    if story.user_id != current_user["uid"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    return _story_to_response(story)


# ── GET /api/stories ──────────────────────────────────────────────────────────

@router.get(
    "/stories",
    response_model=list[StoryResponse],
    summary="List all stories for a user",
)
async def list_stories(
    current_user: CurrentUser,
    db: DbSession,
    user_id: Annotated[
        str,
        Query(description="Firebase UID whose stories to list."),
    ] = "",
) -> list[StoryResponse]:
    """
    Returns all non-deleted stories for the authenticated user, sorted by
    ``created_at`` descending.

    The ``user_id`` query param must match the authenticated token's UID.
    """
    token_uid: str = current_user["uid"]

    # If user_id provided, verify it matches the token
    if user_id and user_id != token_uid:
        raise HTTPException(
            status_code=status.HTTP_403_FORBIDDEN,
            detail="user_id param does not match authenticated token uid.",
        )

    query_uid = user_id or token_uid

    result = await db.execute(
        select(Story)
        .where(
            Story.user_id == query_uid,
            Story.deleted_at.is_(None),
        )
        .order_by(Story.created_at.desc())
    )
    stories: list[Story] = list(result.scalars().all())
    return [_story_to_response(s) for s in stories]


# ── PUT /api/story/{story_id} ─────────────────────────────────────────────────

@router.put(
    "/story/{story_id}",
    response_model=StoryResponse,
    summary="Update story title",
)
async def update_story(
    story_id: str,
    body: StoryUpdateRequest,
    current_user: CurrentUser,
    db: DbSession,
) -> StoryResponse:
    """
    Only the ``title`` field is updatable post-generation.
    """
    try:
        story_uuid = uuid.UUID(story_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid story_id format: {story_id!r}",
        )

    result = await db.execute(
        select(Story).where(
            Story.id == story_uuid,
            Story.deleted_at.is_(None),
        )
    )
    story: Story | None = result.scalar_one_or_none()

    if story is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found.")

    if story.user_id != current_user["uid"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    story.title = body.title
    await db.flush()
    await db.commit()
    await db.refresh(story)

    logger.info("Story %s title updated to %r.", story_id, body.title)
    return _story_to_response(story)


# ── DELETE /api/story/{story_id} ──────────────────────────────────────────────

@router.delete(
    "/story/{story_id}",
    status_code=status.HTTP_204_NO_CONTENT,
    summary="Soft-delete a story",
)
async def delete_story(
    story_id: str,
    current_user: CurrentUser,
    db: DbSession,
) -> None:
    """
    Soft-deletes the story by setting ``deleted_at`` to the current timestamp.
    The record remains in the database but will not appear in list/get queries.
    """
    from datetime import datetime, timezone

    try:
        story_uuid = uuid.UUID(story_id)
    except ValueError:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"Invalid story_id format: {story_id!r}",
        )

    result = await db.execute(
        select(Story).where(
            Story.id == story_uuid,
            Story.deleted_at.is_(None),
        )
    )
    story: Story | None = result.scalar_one_or_none()

    if story is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Story not found.")

    if story.user_id != current_user["uid"]:
        raise HTTPException(status_code=status.HTTP_403_FORBIDDEN, detail="Access denied.")

    story.deleted_at = datetime.now(timezone.utc)
    await db.flush()
    await db.commit()
    logger.info("Story %s soft-deleted.", story_id)
