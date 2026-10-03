"""
Prompt templates and validation helpers for MoonTales LLM providers.
"""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

SYSTEM_PROMPT = """
You are MoonTales, a master children's story author and illustrator briefer.
Your task is to write an enchanting, whimsical, and age-appropriate bedtime story for
children aged 3–8. The story must be safe, positive, soothing, and free of violence,
fear, or adult content.

You will be given a list of story cues (themes, characters, settings) and a
desired page count. For a 5-minute story (around 8 pages), each page must have
a substantial narrative paragraph of 70–95 words (4–6 gentle, engaging sentences)
so that listening to the story feels like a rich, cozy bedtime journey.

You must return a single JSON object (no surrounding markdown, no code fences) with
this exact top-level structure:
{
  "title": "A short, charming title (3-6 words)",
  "pages": [
    ...exactly page_count objects...
  ]
}

Each page object in "pages" MUST have these exact keys:
  "page_number"   — integer starting at 1
  "text"          — the rich story text for this page (70–95 words, 4–6 sentences)
  "audio_text"    — the same story text but with expressive bracket tags
                    naturally inserted: [laughs], [whispers], [gasps],
                    [excited], [sighs], [quietly], [dramatically], [giggles],
                    [warmly]. Place them where a bedtime narrator would naturally
                    express that emotion. Keep the actual words identical to
                    "text" except for the inserted tags.
  "image_prompt"  — a detailed illustration prompt for key scene pages.
                    (NOTE: Pages 1, 3, 5, 7, etc. must have a new SCENE description.
                    Even-numbered pages can reuse the previous scene's prompt or focus
                    on a close-up detail of the same setting). Structure EXACTLY as:

CHARACTER DESIGN (keep exactly consistent across all images): [Full description
of the protagonist's appearance — hair colour, eye colour, clothing colours and
style, distinctive features, art style, lighting palette]
SCENE: [What is happening on this page, the environment, mood, soft bedtime atmosphere]
STYLE: Soft watercolor children's book illustration, warm golden lighting,
whimsical, safe for children, storybook quality

Rules:
- The story must have a clear beginning (pages 1–2), middle adventure/discovery (pages 3 to n-2),
  and a quiet, sleepy, comforting resolution (last 1–2 pages) ideal for falling asleep.
- All pages must form a coherent narrative that flows naturally.
- The protagonist's appearance in EVERY image_prompt must be IDENTICAL in the
  CHARACTER DESIGN block — same wording, same details, every single page.
- Return ONLY the JSON object. No preamble, no explanation, no markdown.
""".strip()


def build_user_prompt(user_cues: list[str], page_count: int) -> str:
    """Format user prompt for story generation."""
    cues_str = ", ".join(user_cues) if user_cues else "magical bedtime adventure"
    return (
        f"Story cues: {cues_str}\n"
        f"Page count: {page_count}\n\n"
        "Generate the story now. Remember: return ONLY the JSON object with "
        f'"title" and exactly {page_count} page objects in "pages".'
    )


def parse_and_validate_pages(
    raw_text: str, expected_page_count: int
) -> tuple[str, list[dict[str, Any]]]:
    """
    Parse JSON text from LLM and validate page schema.
    Returns (title, pages_list).
    Handles accidental markdown fences or wrapper objects.
    """
    text = raw_text.strip()

    # Strip markdown code fences if present
    if text.startswith("```"):
        lines = text.splitlines()
        text = "\n".join(
            line for line in lines if not line.strip().startswith("```")
        ).strip()

    try:
        data = json.loads(text)
    except json.JSONDecodeError as exc:
        # Extract between first '{' and last '}' or '[' and ']'
        start_obj = text.find("{")
        end_obj = text.rfind("}")
        if start_obj != -1 and end_obj != -1 and start_obj < end_obj:
            try:
                data = json.loads(text[start_obj : end_obj + 1])
            except Exception:
                data = None
        else:
            data = None

        if data is None:
            start_arr = text.find("[")
            end_arr = text.rfind("]")
            if start_arr != -1 and end_arr != -1 and start_arr < end_arr:
                try:
                    data = json.loads(text[start_arr : end_arr + 1])
                except Exception:
                    raise RuntimeError(
                        f"LLM returned invalid JSON. Content: {raw_text[:250]}"
                    ) from exc
            else:
                raise RuntimeError(
                    f"LLM returned invalid JSON. Content: {raw_text[:250]}"
                ) from exc

    title = "A MoonTales Bedtime Adventure"
    pages: list[dict[str, Any]] = []

    if isinstance(data, dict):
        if "title" in data and isinstance(data["title"], str) and data["title"].strip():
            title = data["title"].strip()
        for key in ("pages", "story", "data"):
            if key in data and isinstance(data[key], list):
                pages = data[key]
                break
    elif isinstance(data, list):
        pages = data

    if not isinstance(pages, list) or not pages:
        raise RuntimeError(
            f"Expected list of pages from LLM, got {type(pages).__name__}."
        )

    required_keys = {"page_number", "text", "audio_text"}
    for i, page in enumerate(pages):
        if not isinstance(page, dict):
            raise RuntimeError(f"Page item {i + 1} is not a valid object.")
        missing = required_keys - page.keys()
        if missing:
            raise RuntimeError(f"Page {i + 1} from LLM is missing keys: {missing}")
        if "image_prompt" not in page:
            page["image_prompt"] = ""

    # Derive a sensible title if still default
    if title == "A MoonTales Bedtime Adventure" and pages:
        first_sentence = pages[0]["text"].split(".")[0].strip()
        if first_sentence:
            title = first_sentence[:60]

    return title, pages

