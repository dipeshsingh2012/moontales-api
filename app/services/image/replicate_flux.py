"""
Replicate Diffusion Provider — Flux.1 Schnell / SDXL.
"""

import asyncio
import io
import logging

import httpx
import replicate

from app.config import settings
from app.services.image.base import BaseImageProvider

logger = logging.getLogger(__name__)

_MAX_RETRIES = 3
_RETRY_BASE_DELAY = 2.0


class ReplicateImageProvider(BaseImageProvider):
    """Replicate diffusion provider (Flux.1 Schnell / SDXL)."""

    def __init__(
        self,
        api_token: str | None = None,
        model_name: str | None = None,
    ):
        self.api_token = api_token or settings.REPLICATE_API_TOKEN
        self.model_name = (
            model_name or settings.REPLICATE_MODEL or "black-forest-labs/flux-schnell"
        )
        self._client: replicate.Client | None = None

    def _get_client(self) -> replicate.Client:
        if not self.api_token:
            raise ValueError("REPLICATE_API_TOKEN is not configured.")
        if self._client is None:
            self._client = replicate.Client(api_token=self.api_token)
        return self._client

    async def generate_image(
        self,
        image_prompt: str,
        seed: int,
        **kwargs,
    ) -> bytes:
        client = self._get_client()
        last_exc: Exception | None = None

        input_params = {
            "prompt": image_prompt,
            "seed": seed % (2**31 - 1),
            "aspect_ratio": "1:1",
            "output_format": "png",
        }

        for attempt in range(1, _MAX_RETRIES + 1):
            try:
                logger.info(
                    "Replicate (%s) attempt %d/%d seed=%d prompt_len=%d",
                    self.model_name,
                    attempt,
                    _MAX_RETRIES,
                    seed,
                    len(image_prompt),
                )

                # replicate.async_run or async call in thread
                output = await asyncio.to_thread(
                    client.run,
                    self.model_name,
                    input=input_params,
                )

                if not output:
                    raise RuntimeError("Replicate returned empty output.")

                # output is typically a list with a FileOutput or URL
                item = output[0] if isinstance(output, (list, tuple)) else output

                # If item has a .read() method (FileOutput)
                if hasattr(item, "read"):
                    data = item.read()
                    if isinstance(data, bytes):
                        return data

                # If item is a URL string
                item_url = str(item)
                async with httpx.AsyncClient(timeout=60.0) as http_client:
                    res = await http_client.get(item_url)
                    res.raise_for_status()
                    return res.content

            except Exception as exc:
                last_exc = exc
                logger.warning(
                    "Replicate attempt %d failed: %s. Retrying in %.1fs...",
                    attempt,
                    exc,
                    _RETRY_BASE_DELAY * (2 ** (attempt - 1)),
                )
                if attempt < _MAX_RETRIES:
                    await asyncio.sleep(_RETRY_BASE_DELAY * (2 ** (attempt - 1)))

        raise RuntimeError(
            f"Replicate image generation failed after {_MAX_RETRIES} attempts. "
            f"Last error: {last_exc}"
        ) from last_exc
