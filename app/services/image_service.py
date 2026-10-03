"""
Image Service — Swappable Diffusion Façade.

Delegates per-page story illustration generation to the configured
diffusion provider (Google Imagen 3, OpenAI DALL-E, or Replicate Flux/SDXL).
"""

import logging
from app.services.image.factory import get_image_provider

logger = logging.getLogger(__name__)


async def generate_image(
    image_prompt: str,
    seed: int,
    provider: str | None = None,
    **kwargs,
) -> bytes:
    """
    Generate a 1024×1024 story illustration using the configured provider.

    Args:
        image_prompt: The detailed image prompt for this page.
        seed: Random seed for visual character consistency across pages.
        provider: Optional override for provider name ('imagen', 'dalle', 'replicate').

    Returns:
        Raw image bytes.
    """
    image_provider = get_image_provider(provider)
    return await image_provider.generate_image(
        image_prompt=image_prompt, seed=seed, **kwargs
    )
