"""
ElevenLabs TTS Provider — /v1/text-to-speech/{voice_id}/with-timestamps.
"""

import base64
import logging

import httpx

from app.config import settings
from app.services.tts.base import BaseTTSProvider

logger = logging.getLogger(__name__)

_ELEVENLABS_BASE_URL = "https://api.elevenlabs.io"
_MODEL_ID = "eleven_multilingual_v2"
_OUTPUT_FORMAT = "mp3_44100_128"
_REQUEST_TIMEOUT = 120.0  # seconds


class ElevenLabsTTSProvider(BaseTTSProvider):
    """ElevenLabs TTS provider with character-level timing alignment."""

    def __init__(self, api_key: str | None = None, default_voice_id: str | None = None):
        self.api_key = api_key or settings.ELEVENLABS_API_KEY
        self.default_voice_id = default_voice_id or settings.DEFAULT_VOICE_ID

    async def generate_audio(
        self,
        text: str,
        voice_id: str | None = None,
        **kwargs,
    ) -> tuple[bytes, dict]:
        selected_voice_id = voice_id or self.default_voice_id
        if not selected_voice_id:
            raise ValueError(
                "No voice_id provided and DEFAULT_VOICE_ID is not configured for ElevenLabs."
            )
        if not self.api_key:
            raise ValueError("ELEVENLABS_API_KEY is not configured.")

        url = f"{_ELEVENLABS_BASE_URL}/v1/text-to-speech/{selected_voice_id}/with-timestamps"

        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json",
            "Accept": "application/json",
        }

        payload = {
            "text": text,
            "model_id": _MODEL_ID,
            "output_format": _OUTPUT_FORMAT,
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.75,
                "style": 0.0,
                "use_speaker_boost": True,
            },
        }

        logger.info(
            "Calling ElevenLabs TTS with-timestamps. voice_id=%r text_len=%d",
            selected_voice_id,
            len(text),
        )

        async with httpx.AsyncClient(timeout=_REQUEST_TIMEOUT) as client:
            response = await client.post(url, headers=headers, json=payload)

        try:
            response.raise_for_status()
        except httpx.HTTPStatusError as exc:
            logger.error(
                "ElevenLabs TTS error %d: %s",
                exc.response.status_code,
                exc.response.text[:500],
            )
            raise

        data = response.json()

        # ── Decode audio ──────────────────────────────────────────────────────
        audio_base64: str = data.get("audio_base64", "")
        if not audio_base64:
            raise RuntimeError("ElevenLabs response missing 'audio_base64' field.")

        audio_bytes: bytes = base64.b64decode(audio_base64)

        # ── Parse alignment and convert seconds → milliseconds ────────────────
        raw_alignment: dict = data.get("alignment", {})
        characters: list[str] = raw_alignment.get("characters", [])
        start_seconds: list[float] = raw_alignment.get(
            "character_start_times_seconds", []
        )
        end_seconds: list[float] = raw_alignment.get(
            "character_end_times_seconds", []
        )

        alignment: dict = {
            "characters": characters,
            "character_start_times_ms": [t * 1000.0 for t in start_seconds],
            "character_end_times_ms": [t * 1000.0 for t in end_seconds],
        }

        logger.info(
            "ElevenLabs TTS complete. audio_bytes=%d chars=%d",
            len(audio_bytes),
            len(characters),
        )

        return audio_bytes, alignment
