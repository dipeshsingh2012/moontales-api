"""
Gemini LLM Provider — Google GenAI SDK (Gemini 3.8 Flash).
"""

import logging
from typing import Any

from google import genai
from google.genai import types

from app.config import settings
from app.services.llm.base import BaseLLMProvider
from app.services.llm.prompts import (
    SYSTEM_PROMPT,
    build_user_prompt,
    parse_and_validate_pages,
)

logger = logging.getLogger(__name__)


class GeminiLLMProvider(BaseLLMProvider):
    """Generates story pages via Google Gemini 3.8 Flash using the modern google-genai SDK."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str = "gemini-3.8-flash",
    ):
        self.api_key = api_key or settings.GOOGLE_AI_API_KEY
        self.model_name = model_name
        self._client: genai.Client | None = None

    def _get_client(self) -> genai.Client:
        if not self.api_key:
            raise ValueError("GOOGLE_AI_API_KEY is not configured for Gemini provider.")
        if self._client is None:
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    async def generate_story_pages(
        self,
        user_cues: list[str],
        page_count: int,
        **kwargs,
    ) -> tuple[str, list[dict[str, Any]]]:
        client = self._get_client()
        user_prompt = build_user_prompt(user_cues, page_count)

        logger.info(
            "Calling Gemini (%s) for story generation. cues=%r page_count=%d",
            self.model_name,
            user_cues,
            page_count,
        )

        response = await client.aio.models.generate_content(
            model=self.model_name,
            contents=user_prompt,
            config=types.GenerateContentConfig(
                system_instruction=SYSTEM_PROMPT,
                response_mime_type="application/json",
                temperature=0.9,
                top_p=0.95,
                max_output_tokens=16384,
            ),
        )

        raw_text: str = (response.text or "").strip()
        title, pages = parse_and_validate_pages(raw_text, page_count)
        logger.info("Gemini returned %d pages with title %r.", len(pages), title)
        return title, pages
