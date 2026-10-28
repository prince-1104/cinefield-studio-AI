"""Abstract base class for media renderers."""

from abc import ABC, abstractmethod


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
        captions: list[dict[str, str | float]] | None = None,
    ) -> str:
        """Render clips, audio, brand logo, and CTA into a finished MP4 advertisement.

        Args:
            clip_paths: List of file paths to generated video clips in shot sequence.
            narration_path: File path to voiceover narration audio.
            output_path: File path for the final assembled MP4.
            music_path: Optional background music audio file.
            logo_path: Optional brand logo image for composite watermark/outro.
            cta_text: Optional Call-To-Action text for end card overlay.
            captions: Optional timed subtitle cue blocks.

        Returns:
            The path to the rendered MP4 file.
        """
        pass

