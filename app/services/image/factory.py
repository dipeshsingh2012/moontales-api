"""
Image Diffusion Provider Factory.
"""

import logging
from app.config import settings
from app.services.image.base import BaseImageProvider
from app.services.image.imagen import ImagenProvider
from app.services.image.dalle import DalleProvider
from app.services.image.replicate_flux import ReplicateImageProvider

logger = logging.getLogger(__name__)

_PROVIDERS: dict[str, type[BaseImageProvider]] = {
    "imagen": ImagenProvider,
    "dalle": DalleProvider,
    "replicate": ReplicateImageProvider,
}


def get_image_provider(provider_name: str | None = None) -> BaseImageProvider:
    """
    Return an Image diffusion provider instance based on provider_name or settings.IMAGE_PROVIDER.
    """
    name = (provider_name or settings.IMAGE_PROVIDER).strip().lower()
    provider_cls = _PROVIDERS.get(name)
    if not provider_cls:
        raise ValueError(
            f"Unsupported Image provider: {name!r}. Supported providers: {list(_PROVIDERS.keys())}"
        )
    return provider_cls()
