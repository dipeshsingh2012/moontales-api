from abc import ABC, abstractmethod
from typing import Any


class BaseLLMProvider(ABC):
    """Abstract base class for LLM story generation providers."""

    @abstractmethod
    async def generate_story_pages(
        self,
        user_cues: list[str],
        page_count: int,
        **kwargs,
    ) -> tuple[str, list[dict[str, Any]]]:
        """
        Generate structured story page data from cues.

        Args:
            user_cues: List of story themes/characters.
            page_count: Desired number of story pages.

        Returns:
            Tuple of (title, list of page dicts with keys: page_number, text, audio_text, image_prompt).
        """
        pass
