"""
Audio Service — Swappable TTS Façade.

Delegates to active TTS provider (GCP Cloud TTS or ElevenLabs).
Returns (audio_bytes, alignment) where alignment matches the mobile schema.
"""

import logging
from app.services.tts.factory import get_tts_provider

logger = logging.getLogger(__name__)


async def generate_audio(
    text: str,
    voice_id: str | None = None,
    provider: str | None = None,
    **kwargs,
) -> tuple[bytes, dict]:
    """
    Synthesize speech using the configured TTS provider.

    Args:
        text: Story page text with bracketed emotion tags.
        voice_id: Optional provider-specific voice identifier.
        provider: Optional override for provider name ('gcp' or 'elevenlabs').
        **kwargs: Extra parameters passed to provider (e.g. legacy xi_api_key).

    Returns:
        tuple[bytes, dict]: (audio_bytes, alignment)
    """
    tts_provider = get_tts_provider(provider)
    return await tts_provider.generate_audio(text=text, voice_id=voice_id, **kwargs)
