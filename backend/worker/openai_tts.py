"""OpenAI Text-To-Speech implementation of SpeechProvider."""

import logging
from pathlib import Path

from openai import OpenAI

from app.config import settings
from app.interfaces.speech_provider import SpeechProvider

logger = logging.getLogger(__name__)


class OpenAISpeechProvider(SpeechProvider):
    """Synthesizes voiceover narration using OpenAI's Speech API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        voice: str | None = None,
    ) -> None:
        self.api_key = api_key or settings.OPENAI_API_KEY
        self.model = model or settings.OPENAI_TTS_MODEL
        self.voice = voice or settings.OPENAI_TTS_VOICE
        self._client: OpenAI | None = None

    @property
    def client(self) -> OpenAI:
        if not self.api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not configured. "
                "Please configure a valid OpenAI API key in your .env file to generate speech narration."
            )
        if self._client is None:
            self._client = OpenAI(api_key=self.api_key)
        return self._client

    async def synthesize(
        self,
        text: str,
        output_path: str,
        voice: str | None = None,
        instructions: str | None = None,
    ) -> str:
        """Synthesize voiceover narration and write the audio file."""
        if not text or not text.strip():
            raise ValueError("Cannot synthesize speech: text is empty.")

        dest = Path(output_path).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)
        selected_voice = voice or self.voice

        logger.info(
            f"Synthesizing speech with model={self.model}, voice={selected_voice}: "
            f"'{text[:60]}...' -> {dest}"
        )

        kwargs: dict = {
            "model": self.model,
            "voice": selected_voice,
            "input": text.strip(),
            "response_format": "mp3",
        }

        # The gpt-4o-mini-tts model supports instructions for expressive steering
        if instructions and "mini-tts" in self.model:
            kwargs["instructions"] = instructions

        response = self.client.audio.speech.create(**kwargs)

        # Write audio stream to destination file
        if hasattr(response, "stream_to_file"):
            response.stream_to_file(str(dest))
        elif hasattr(response, "read"):
            dest.write_bytes(response.read())
        elif hasattr(response, "content"):
            dest.write_bytes(response.content)
        else:
            # Fallback using response iterator
            with open(dest, "wb") as f:
                for chunk in response.iter_bytes():
                    f.write(chunk)

        logger.info(f"Successfully generated narration audio file at {dest}")
        return str(dest)

