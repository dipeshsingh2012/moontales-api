from abc import ABC, abstractmethod


class BaseImageProvider(ABC):
    """Abstract base class for per-page story illustration diffusion models."""

    @abstractmethod
    async def generate_image(
        self,
        image_prompt: str,
        seed: int,
        **kwargs,
    ) -> bytes:
        """
        Generate a single page illustration.

        Args:
            image_prompt: Detailed prompt containing CHARACTER DESIGN, SCENE, and STYLE.
            seed: Integer seed to maintain visual character consistency across pages.

        Returns:
            Raw image bytes (PNG or JPEG).
        """
        pass
