"""
OpenAI LLM Provider — GPT-4o / GPT-4o-mini.
"""

import logging
from typing import Any

from openai import AsyncOpenAI

from app.config import settings
from app.services.llm.base import BaseLLMProvider
from app.services.llm.prompts import (
    SYSTEM_PROMPT,
    build_user_prompt,
    parse_and_validate_pages,
)

logger = logging.getLogger(__name__)


class OpenAILLMProvider(BaseLLMProvider):
    """Generates story pages via OpenAI Chat Completions API."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
    ):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model_name = model_name or settings.OPENAI_LLM_MODEL or "gpt-4o-mini"
        self._client: AsyncOpenAI | None = None

    def _get_client(self) -> AsyncOpenAI:
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is not configured.")
        if self._client is None:
            self._client = AsyncOpenAI(api_key=self.api_key)
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
            "Calling OpenAI (%s) for story generation. cues=%r page_count=%d",
            self.model_name,
            user_cues,
            page_count,
        )

        response = await client.chat.completions.create(
            model=self.model_name,
            messages=[
                {"role": "system", "content": SYSTEM_PROMPT},
                {"role": "user", "content": user_prompt},
            ],
            response_format={"type": "json_object"},
            temperature=0.85,
        )

        raw_text = response.choices[0].message.content or ""
        title, pages = parse_and_validate_pages(raw_text, page_count)
        logger.info("OpenAI returned %d pages with title %r.", len(pages), title)
        return title, pages
