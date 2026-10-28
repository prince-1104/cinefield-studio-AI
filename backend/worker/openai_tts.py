"""OpenAI Text-To-Speech implementation of SpeechProvider."""

import logging
from pathlib import Path

from openai import AsyncOpenAI

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
        raw_key = api_key if api_key is not None else settings.OPENAI_API_KEY
        self.api_key = raw_key.strip().rstrip(",") if raw_key else ""
        self.model = model or settings.OPENAI_TTS_MODEL
        self.voice = voice or settings.OPENAI_TTS_VOICE
        self._client: AsyncOpenAI | None = None

    @property
    def client(self) -> AsyncOpenAI:
        if not self.api_key:
            raise RuntimeError(
                "OPENAI_API_KEY is not configured. "
                "Please configure a valid OpenAI API key in your .env file to generate speech narration."
            )
        if self._client is None:
            self._client = AsyncOpenAI(api_key=self.api_key)
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

        response = await self.client.audio.speech.create(**kwargs)

        # Write audio stream to destination file
        if hasattr(response, "content") and response.content:
            dest.write_bytes(response.content)
        elif hasattr(response, "aread"):
            dest.write_bytes(await response.aread())
        elif hasattr(response, "read"):
            dest.write_bytes(response.read())
        elif hasattr(response, "stream_to_file"):
            response.stream_to_file(str(dest))
        else:
            with open(dest, "wb") as f:
                async for chunk in response.aiter_bytes():
                    f.write(chunk)

        logger.info(f"Successfully generated narration audio file at {dest}")
        return str(dest)

