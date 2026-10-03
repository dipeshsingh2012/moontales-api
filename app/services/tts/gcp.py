"""
Google Cloud Text-to-Speech Provider.

Uses GCP Text-to-Speech API (Journey/Neural2/Studio voices).
Provides character-level alignment estimation and cleans emotion cues.
"""

import io
import json
import logging
import re
from typing import Any

from google.cloud import texttospeech
from google.oauth2 import service_account

from app.config import settings
from app.services.tts.base import BaseTTSProvider

logger = logging.getLogger(__name__)


def estimate_mp3_duration_ms(mp3_bytes: bytes) -> float:
    """
    Estimate or calculate MP3 audio duration in milliseconds from raw MP3 bytes.
    Parses MPEG-1, MPEG-2, and MPEG-2.5 Layer III frame headers accurately.
    """
    if not mp3_bytes:
        return 0.0

    # Bitrate tables in kbps for Layer III
    bitrates_v1_l3 = [0, 32, 40, 48, 56, 64, 80, 96, 112, 128, 160, 192, 224, 256, 320, 0]
    bitrates_v2_l3 = [0, 8, 16, 24, 32, 40, 48, 56, 64, 80, 96, 112, 128, 144, 160, 0]

    samplerates_v1 = [44100, 48000, 32000, 0]
    samplerates_v2 = [22050, 24000, 16000, 0]
    samplerates_v25 = [11025, 12000, 8000, 0]

    offset = 0
    total_length = len(mp3_bytes)
    total_duration_sec = 0.0
    frames_found = 0

    while offset < total_length - 4:
        if mp3_bytes[offset] == 0xFF and (mp3_bytes[offset + 1] & 0xE0) == 0xE0:
            b1 = mp3_bytes[offset + 1]
            b2 = mp3_bytes[offset + 2]

            version_idx = (b1 >> 3) & 0x03  # 3=MPEG-1, 2=MPEG-2, 0=MPEG-2.5
            layer_idx = (b1 >> 1) & 0x03    # 1=Layer III

            if version_idx != 1 and layer_idx == 1:
                bitrate_idx = (b2 >> 4) & 0x0F
                samplerate_idx = (b2 >> 2) & 0x03
                padding = (b2 >> 1) & 0x01

                if bitrate_idx not in (0, 15) and samplerate_idx != 3:
                    if version_idx == 3:
                        br = bitrates_v1_l3[bitrate_idx] * 1000
                        sr = samplerates_v1[samplerate_idx]
                        samples = 1152
                        frame_size = int((144 * br) / sr) + padding
                    else:
                        br = bitrates_v2_l3[bitrate_idx] * 1000
                        sr = samplerates_v2[samplerate_idx] if version_idx == 2 else samplerates_v25[samplerate_idx]
                        samples = 576
                        frame_size = int((72 * br) / sr) + padding

                    if frame_size > 0:
                        total_duration_sec += samples / sr
                        frames_found += 1
                        offset += frame_size
                        continue
        offset += 1

    if frames_found > 0:
        return total_duration_sec * 1000.0

    # Fallback heuristic: 32 kbps (GCP TTS default) or 64 kbps
    duration_sec = len(mp3_bytes) / 4000.0
    return max(duration_sec * 1000.0, 500.0)


def generate_character_alignment(
    text: str, total_duration_ms: float
) -> dict[str, Any]:
    """
    Generate character-level timing alignment interpolated over total duration,
    allocating slightly more weight to punctuation pauses.
    """
    chars = list(text)
    if not chars:
        return {
            "characters": [],
            "character_start_times_ms": [],
            "character_end_times_ms": [],
        }

    # Weight characters: punctuation pauses get higher relative duration
    weights = []
    for c in chars:
        if c in ".!?":
            weights.append(3.5)
        elif c in ",;:":
            weights.append(2.0)
        elif c == " ":
            weights.append(1.0)
        else:
            weights.append(1.0)

    total_weight = sum(weights) or 1.0
    ms_per_weight = total_duration_ms / total_weight

    start_times = []
    end_times = []
    current_time = 0.0

    for w in weights:
        duration = w * ms_per_weight
        start_times.append(round(current_time, 2))
        current_time += duration
        end_times.append(round(current_time, 2))

    return {
        "characters": chars,
        "character_start_times_ms": start_times,
        "character_end_times_ms": end_times,
    }


class GCPTTSProvider(BaseTTSProvider):
    """Google Cloud Text-to-Speech synthesis provider."""

    def __init__(
        self,
        default_voice_name: str | None = None,
        language_code: str | None = None,
    ):
        self.default_voice_name = (
            default_voice_name or settings.GCP_TTS_VOICE_NAME or "en-US-Journey-F"
        )
        self.default_language_code = (
            language_code or settings.GCP_TTS_LANGUAGE_CODE or "en-US"
        )
        self._client: texttospeech.TextToSpeechAsyncClient | None = None

    def _get_client(self) -> texttospeech.TextToSpeechAsyncClient:
        if self._client is None:
            if settings.FIREBASE_SERVICE_ACCOUNT_JSON.strip():
                try:
                    info = json.loads(settings.FIREBASE_SERVICE_ACCOUNT_JSON)
                    creds = service_account.Credentials.from_service_account_info(
                        info
                    )
                    self._client = texttospeech.TextToSpeechAsyncClient(
                        credentials=creds
                    )
                    return self._client
                except Exception as exc:
                    logger.warning(
                        "Could not parse FIREBASE_SERVICE_ACCOUNT_JSON for GCP TTS: %s. Using default credentials.",
                        exc,
                    )
            self._client = texttospeech.TextToSpeechAsyncClient()
        return self._client

    async def generate_audio(
        self,
        text: str,
        voice_id: str | None = None,
        **kwargs,
    ) -> tuple[bytes, dict]:
        """
        Synthesize speech with GCP TTS and return (audio_bytes, alignment).
        """
        # Clean emotion bracket tags (e.g. "[whispers]", "[laughs]")
        cleaned_text = re.sub(r"\[.*?\]", "", text)
        # Collapse multiple spaces
        cleaned_text = re.sub(r"\s+", " ", cleaned_text).strip()
        if not cleaned_text:
            cleaned_text = text

        voice_name = voice_id or self.default_voice_name

        # Extract language code from voice_name prefix if formatted like 'en-US-Journey-F'
        parts = voice_name.split("-")
        if len(parts) >= 2 and len(parts[0]) == 2 and len(parts[1]) == 2:
            language_code = f"{parts[0]}-{parts[1]}"
        else:
            language_code = self.default_language_code

        logger.info(
            "Calling GCP Cloud TTS. voice=%s language=%s text_len=%d",
            voice_name,
            language_code,
            len(cleaned_text),
        )

        client = self._get_client()

        synthesis_input = texttospeech.SynthesisInput(text=cleaned_text)
        voice = texttospeech.VoiceSelectionParams(
            language_code=language_code,
            name=voice_name,
        )
        audio_config = texttospeech.AudioConfig(
            audio_encoding=texttospeech.AudioEncoding.MP3,
            speaking_rate=0.95,  # gentle pacing for bedtime storytelling
            pitch=0.0,
        )

        response = await client.synthesize_speech(
            input=synthesis_input,
            voice=voice,
            audio_config=audio_config,
        )

        audio_bytes = response.audio_content
        if not audio_bytes:
            raise RuntimeError("GCP TTS returned empty audio content.")

        # Estimate duration and build character alignment
        total_duration_ms = estimate_mp3_duration_ms(audio_bytes)
        alignment = generate_character_alignment(cleaned_text, total_duration_ms)

        logger.info(
            "GCP TTS complete. audio_bytes=%d duration_ms=%.1f chars=%d",
            len(audio_bytes),
            total_duration_ms,
            len(alignment["characters"]),
        )

        return audio_bytes, alignment
