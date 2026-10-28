"""Gemini Omni Flash implementation of VideoGenerationProvider using the Interactions API."""

import base64
import logging
from pathlib import Path

from google import genai
from google.genai import types

from app.config import settings
from app.interfaces.video_generator import VideoGenerationProvider

logger = logging.getLogger(__name__)


class GeminiOmniVideoGenerator(VideoGenerationProvider):
    """Generates video clips using Gemini Omni Flash (gemini-omni-1.1-flash) via the Interactions API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
    ) -> None:
        self.api_key = api_key or settings.GEMINI_API_KEY
        self.model = model or settings.GEMINI_VIDEO_MODEL
        self._client: genai.Client | None = None

    @property
    def client(self) -> genai.Client:
        if not self.api_key:
            raise RuntimeError(
                "GEMINI_API_KEY is not configured. "
                "Please configure a valid Google Gemini API key in your .env file to generate video clips."
            )
        if self._client is None:
            self._client = genai.Client(api_key=self.api_key)
        return self._client

    async def generate_clip(
        self,
        prompt: str,
        output_path: str,
        reference_image_path: str | None = None,
        duration_seconds: int = 5,
        aspect_ratio: str = "16:9",
    ) -> str:
        """Generate a video clip using Gemini Omni Flash via the Interactions API."""
        dest = Path(output_path).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"Generating video clip with model {self.model}: '{prompt[:60]}...' "
            f"(target: {dest})"
        )

        input_payload: list | str
        if reference_image_path and Path(reference_image_path).is_file():
            ref_path = Path(reference_image_path)
            image_bytes = ref_path.read_bytes()
            image_part = types.Part.from_bytes(
                data=image_bytes,
                mime_type="image/png",
            )
            input_payload = [
                image_part,
                (
                    f"Generate a {duration_seconds}-second cinematic video clip in {aspect_ratio} aspect ratio. "
                    f"Visual direction: {prompt}"
                ),
            ]
        else:
            input_payload = (
                f"Generate a {duration_seconds}-second cinematic video clip in {aspect_ratio} aspect ratio. "
                f"Visual direction: {prompt}"
            )

        # Call Gemini Omni Flash via the Interactions API
        interaction = self.client.interactions.create(
            model=self.model,
            input=input_payload,
        )

        video_bytes: bytes | None = None

        # Check interaction response fields for video payload
        if hasattr(interaction, "output_video") and interaction.output_video:
            out_vid = interaction.output_video
            if hasattr(out_vid, "data"):
                data = out_vid.data
                video_bytes = base64.b64decode(data) if isinstance(data, str) else data
            elif hasattr(out_vid, "bytes"):
                video_bytes = out_vid.bytes
        elif hasattr(interaction, "outputs") and interaction.outputs:
            for out in interaction.outputs:
                if getattr(out, "type", None) == "video" or hasattr(out, "video"):
                    vid_data = getattr(out, "data", None) or getattr(out, "video", None)
                    if isinstance(vid_data, str):
                        video_bytes = base64.b64decode(vid_data)
                    elif isinstance(vid_data, bytes):
                        video_bytes = vid_data
                    break
        elif hasattr(interaction, "candidates") and interaction.candidates:
            # Fallback check on standard candidate parts
            for part in interaction.candidates[0].content.parts:
                if hasattr(part, "inline_data") and part.inline_data:
                    video_bytes = base64.b64decode(part.inline_data.data)
                    break

        if not video_bytes:
            raise RuntimeError(
                f"Gemini Omni Flash interaction completed but did not return video bytes. "
                f"Response attributes: {dir(interaction)}"
            )

        dest.write_bytes(video_bytes)
        logger.info(f"Successfully saved video clip to {dest} ({len(video_bytes)} bytes)")
        return str(dest)
