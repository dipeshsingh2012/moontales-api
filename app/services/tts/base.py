from abc import ABC, abstractmethod


class BaseTTSProvider(ABC):
    """Abstract base class for Text-to-Speech synthesis providers."""

    @abstractmethod
    async def generate_audio(
        self,
        text: str,
        voice_id: str | None = None,
        **kwargs,
    ) -> tuple[bytes, dict]:
        """
        Synthesize speech from story text.

        Args:
            text: Story text (may include bracket emotion tags like [laughs], [whispers]).
            voice_id: Optional provider-specific voice identifier.

        Returns:
            A tuple of (audio_bytes, alignment_dict) where alignment_dict contains:
                - "characters": list[str]
                - "character_start_times_ms": list[float]
                - "character_end_times_ms": list[float]
        """
        pass
