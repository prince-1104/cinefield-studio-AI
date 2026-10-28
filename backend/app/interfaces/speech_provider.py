"""Abstract base class for speech synthesis providers."""

from abc import ABC, abstractmethod


class SpeechProvider(ABC):
    """Interface for text-to-speech audio narration synthesis."""

    @abstractmethod
    async def synthesize(
        self,
        text: str,
        output_path: str,
        voice: str | None = None,
        instructions: str | None = None,
    ) -> str:
        """Synthesize narration speech from text.

        Args:
            text: Narration copy to speak.
            output_path: Destination path for the generated audio file (.mp3 / .aac).
            voice: Voice identifier (e.g., 'coral', 'alloy').
            instructions: Optional stylistic steering for tone and pacing.

        Returns:
            The output path of the generated audio file.
        """
        pass

