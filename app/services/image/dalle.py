"""
OpenAI DALL-E Provider.

Generates 1024×1024 story illustrations via OpenAI Images API (DALL-E 3).
"""

import asyncio
import base64
import logging

from openai import AsyncOpenAI

from app.config import settings
from app.services.image.base import BaseImageProvider

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 2.0


class DalleProvider(BaseImageProvider):
    """OpenAI DALL-E image generation provider."""

    def __init__(
        self,
        api_key: str | None = None,
        model_name: str | None = None,
    ):
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model_name = model_name or settings.DALL_E_MODEL or "dall-e-3"
        self._client: AsyncOpenAI | None = None

    def _get_client(self) -> AsyncOpenAI:
        if not self.api_key:
            raise ValueError("OPENAI_API_KEY is not configured for DALL-E.")
        if self._client is None:
            self._client = AsyncOpenAI(api_key=self.api_key)
        return self._client

    async def generate_image(
        self,
        image_prompt: str,
        seed: int,
        **kwargs,
    ) -> bytes:
        client = self._get_client()
        last_exc: Exception | None = None

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                logger.info(
                    "DALL-E attempt %d/%d for prompt_len=%d",
                    attempt,
                    _MAX_RETRIES,
                    len(image_prompt),
                )

                response = await client.images.generate(
                    model=self.model_name,
                    prompt=image_prompt,
                    size="1024x1024",
                    quality="standard",
                    response_format="b64_json",
                    n=1,
                )

                if not response.data or not response.data[0].b64_json:
                    raise RuntimeError("DALL-E returned no image data.")

                image_bytes = base64.b64decode(response.data[0].b64_json)
                logger.info(
                    "DALL-E generated image successfully on attempt %d.", attempt
                )
                return image_bytes

            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "DALL-E attempt %d failed: %s. Retrying in %.1fs...",
                    attempt,
                    exc,
                    _RETRY_BASE_DELAY * (2 ** (attempt - 1)),
                )
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(_RETRY_BASE_DELAY * (2 ** (attempt - 1)))

        raise RuntimeError(
            f"DALL-E image generation failed after {_MAX_RETRIES} attempts. "
            f"Last error: {last_exc}"
        ) from last_exc
