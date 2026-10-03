import pytest
from unittest.mock import AsyncMock, patch, MagicMock

from app.services.tts.factory import get_tts_provider
from app.services.tts.gcp import (
    GCPTTSProvider,
    estimate_mp3_duration_ms,
    generate_character_alignment,
)
from app.services.tts.elevenlabs import ElevenLabsTTSProvider
from app.services import audio_service


def test_get_tts_provider_factory():
    gcp_provider = get_tts_provider("gcp")
    assert isinstance(gcp_provider, GCPTTSProvider)

    el_provider = get_tts_provider("elevenlabs")
    assert isinstance(el_provider, ElevenLabsTTSProvider)

    with pytest.raises(ValueError, match="Unsupported TTS provider"):
        get_tts_provider("unknown_provider")


def test_generate_character_alignment():
    text = "Hello, world!"
    duration_ms = 1000.0
    alignment = generate_character_alignment(text, duration_ms)

    assert alignment["characters"] == list(text)
    assert len(alignment["character_start_times_ms"]) == len(text)
    assert len(alignment["character_end_times_ms"]) == len(text)
    # Start of first character should be 0.0
    assert alignment["character_start_times_ms"][0] == 0.0
    # End of last character should be close to duration_ms
    assert abs(alignment["character_end_times_ms"][-1] - duration_ms) < 5.0


def test_estimate_mp3_duration_ms():
    # Empty bytes
    assert estimate_mp3_duration_ms(b"") == 0.0
    # Fallback with dummy bytes
    dummy_mp3 = b"\x00" * 32000
    duration = estimate_mp3_duration_ms(dummy_mp3)
    assert duration > 0


@pytest.mark.asyncio
async def test_gcp_tts_synthesis_flow():
    provider = GCPTTSProvider(default_voice_name="en-US-Journey-F")

    mock_client = MagicMock()
    mock_response = MagicMock()
    mock_response.audio_content = b"\xFF\xFB\x90\x44" + b"\x00" * 5000
    mock_client.synthesize_speech = AsyncMock(return_value=mock_response)

    with patch.object(provider, "_get_client", return_value=mock_client):
        audio_bytes, alignment = await provider.generate_audio(
            text="Once upon a time [laughs] in a forest."
        )

        assert audio_bytes == mock_response.audio_content
        assert "characters" in alignment
        assert "character_start_times_ms" in alignment
        assert "character_end_times_ms" in alignment
        # Bracket tag [laughs] should be cleaned from alignment
        assert "[" not in alignment["characters"]
        assert "]" not in alignment["characters"]


@pytest.mark.asyncio
async def test_audio_service_facade():
    mock_provider = MagicMock()
    mock_provider.generate_audio = AsyncMock(
        return_value=(b"audio_data", {"characters": ["a"]})
    )

    with patch("app.services.audio_service.get_tts_provider", return_value=mock_provider):
        audio, alignment = await audio_service.generate_audio("Hello", voice_id="v1")
        assert audio == b"audio_data"
        assert alignment == {"characters": ["a"]}
        mock_provider.generate_audio.assert_awaited_once_with(
            text="Hello", voice_id="v1"
        )
