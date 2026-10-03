"""
LLM Service — Swappable LLM Façade.

Delegates story generation to the configured LLM provider (Gemini, OpenAI, or Groq).
Returns a structured list of story page dicts.
"""

import logging
from typing import Any

from app.services.llm.factory import get_llm_provider

logger = logging.getLogger(__name__)


async def generate_story_pages(
    user_cues: list[str],
    page_count: int,
    provider: str | None = None,
    **kwargs,
) -> tuple[str, list[dict[str, Any]]]:
    """
    Generate structured story page data using the configured LLM provider.

    Args:
        user_cues: List of story themes/characters.
        page_count: Number of story pages to generate.
        provider: Optional override for provider name ('gemini', 'openai', 'groq').

    Returns:
        Tuple of (title, list of page dicts with keys: page_number, text, audio_text, image_prompt).
    """
    llm_provider = get_llm_provider(provider)
    return await llm_provider.generate_story_pages(
        user_cues=user_cues, page_count=page_count, **kwargs
    )

