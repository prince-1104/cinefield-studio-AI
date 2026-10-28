"""Abstract base class for media renderers."""

from abc import ABC, abstractmethod
from typing import Any


class MediaRenderer(ABC):
    """Interface for assembling video clips, audio, captions, and brand assets."""

    @abstractmethod
    async def render_advertisement(
        self,
        clip_paths: list[str],
        narration_path: str,
        output_path: str,
        music_path: str | None = None,
        logo_path: str | None = None,
        cta_text: str | None = None,
        captions: list[dict[str, Any]] | None = None,
        aspect_ratio: str = "16:9",
        target_duration: int | None = None,
    ) -> str:
        """Render clips, audio, brand logo, captions, and CTA into a finished MP4 advertisement.

        Args:
            clip_paths: List of file paths to generated video clips in storyboard sequence.
            narration_path: File path to voiceover narration audio.
            output_path: File path for the final assembled MP4.
            music_path: Optional background music audio file.
            logo_path: Optional brand logo image for composite watermark/outro.
            cta_text: Optional Call-To-Action text for end card overlay.
            captions: Optional timed subtitle cue blocks.
            aspect_ratio: "16:9" or "9:16".
            target_duration: Planned duration in seconds.

        Returns:
            The path to the rendered MP4 file.
        """
        pass

    @abstractmethod
    async def render_timeline(
        self,
        timeline_data: dict[str, Any],
        output_path: str,
    ) -> str:
        """Render a customized multitrack timeline composition into a finished MP4.

        Supports clip reordering, source trimming, audio gains/fades, logo positioning,
        and caption overlays according to the canonical timeline model.
        """
        pass
