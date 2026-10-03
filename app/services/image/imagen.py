"""
Google Image Provider — Modern Google GenAI SDK.

Generates story page illustrations via Google AI using the active image generation models.
"""

import asyncio
import logging

from google import genai

from app.config import settings
from app.services.image.base import BaseImageProvider

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "gemini-2.5-flash-image"
_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 2.0  # seconds


class ImagenProvider(BaseImageProvider):
    """Google Gemini illustration generation provider using google-genai SDK."""

    def __init__(self, api_key: str | None = None, model_name: str = _DEFAULT_MODEL):
        self.api_key = api_key or settings.GOOGLE_AI_API_KEY
        self.model_name = model_name
        self._client: genai.Client | None = None

    def _get_client(self) -> genai.Client:
        if not self.api_key:
            raise ValueError("GOOGLE_AI_API_KEY is not configured for Image generation.")
        if self._client is None:
            self._client = genai.Client(api_key=self.api_key)
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
                    "Google Image generation attempt %d/%d (model=%s, seed=%d)",
                    attempt,
                    _MAX_RETRIES,
                    self.model_name,
                    seed,
                )

                response = await client.aio.models.generate_content(
                    model=self.model_name,
                    contents=f"Generate a storybook illustration for children: {image_prompt}",
                )

                if response.candidates and response.candidates[0].content:
                    for part in response.candidates[0].content.parts:
                        if hasattr(part, "inline_data") and part.inline_data and part.inline_data.data:
                            logger.info("Generated image successfully on attempt %d.", attempt)
                            return part.inline_data.data

                raise RuntimeError("No image data returned in Gemini image response.")

            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "Image attempt %d failed: %s. Retrying in %.1fs...",
                    attempt,
                    exc,
                    _RETRY_BASE_DELAY * (2 ** (attempt - 1)),
                )
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(_RETRY_BASE_DELAY * (2 ** (attempt - 1)))

        raise RuntimeError(
            f"Image generation failed after {_MAX_RETRIES} attempts. Last error: {last_exc}"
        ) from last_exc
