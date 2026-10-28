"""Abstract base class for video generation providers."""

from abc import ABC, abstractmethod


class VideoGenerationProvider(ABC):
    """Interface for generating cinematic video clips."""

    @abstractmethod
    async def generate_clip(
        self,
        prompt: str,
        output_path: str,
        reference_image_path: str | None = None,
        duration_seconds: int = 5,
        aspect_ratio: str = "16:9",
    ) -> str:
        """Generate a video clip from a text prompt and optional reference image.

        Args:
            prompt: Visual direction prompt for the clip.
            output_path: Destination filesystem path for the generated MP4.
            reference_image_path: Optional path to product or character reference image.
            duration_seconds: Target clip duration.
            aspect_ratio: Video aspect ratio ('16:9' or '9:16').

        Returns:
            The output path of the generated video clip.
        """
        pass

