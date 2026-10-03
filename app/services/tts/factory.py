"""
TTS Provider Factory.
"""

import logging
from app.config import settings
from app.services.tts.base import BaseTTSProvider
from app.services.tts.elevenlabs import ElevenLabsTTSProvider
from app.services.tts.gcp import GCPTTSProvider

logger = logging.getLogger(__name__)

_PROVIDERS: dict[str, type[BaseTTSProvider]] = {
    "gcp": GCPTTSProvider,
    "elevenlabs": ElevenLabsTTSProvider,
}


def get_tts_provider(provider_name: str | None = None) -> BaseTTSProvider:
    """
    Return a TTS provider instance based on provider_name or settings.TTS_PROVIDER.
    """
    name = (provider_name or settings.TTS_PROVIDER).strip().lower()
    provider_cls = _PROVIDERS.get(name)
    if not provider_cls:
        raise ValueError(
            f"Unsupported TTS provider: {name!r}. Supported providers: {list(_PROVIDERS.keys())}"
        )
    return provider_cls()
