"""Gemini Omni Flash implementation of VideoGenerationProvider using the Interactions API."""

import asyncio
import base64
import logging
import mimetypes
from pathlib import Path
from typing import Any

from google import genai
import httpx

from app.config import settings
from app.interfaces.video_generator import VideoGenerationProvider

logger = logging.getLogger(__name__)


class GeminiOmniVideoGenerator(VideoGenerationProvider):
    """Generates video clips using Gemini Omni Flash (gemini-omni-1.1-flash) via the Interactions API."""

    def __init__(
        self,
        api_key: str | None = None,
        model: str | None = None,
        poll_interval_seconds: float = 3.0,
        timeout_seconds: float = 300.0,
    ) -> None:
        raw_key = api_key if api_key is not None else settings.GEMINI_API_KEY
        self.api_key = raw_key.strip().rstrip(",") if raw_key else ""
        self.model = model or settings.GEMINI_VIDEO_MODEL
        self.poll_interval = poll_interval_seconds
        self.timeout = timeout_seconds
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
        """Generate a video clip using Gemini Omni Flash via the Interactions API.
        
        Handles multimodal image conditioning, asynchronous interaction polling,
        and binary video decoding or remote URI downloading.
        """
        dest = Path(output_path).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)

        logger.info(
            f"Requesting video generation with model={self.model}, "
            f"aspect_ratio={aspect_ratio}, duration={duration_seconds}s (target: {dest.name})"
        )

        direction_text = (
            f"Generate a {duration_seconds}-second cinematic video clip in {aspect_ratio} aspect ratio. "
            f"Visual direction: {prompt}"
        )

        input_payload: Any
        if reference_image_path and Path(reference_image_path).is_file():
            ref_path = Path(reference_image_path)
            mime_type, _ = mimetypes.guess_type(str(ref_path))
            mime_type = mime_type or "image/png"
            image_b64 = base64.b64encode(ref_path.read_bytes()).decode("utf-8")
            input_payload = [
                {
                    "type": "image",
                    "data": image_b64,
                    "mime_type": mime_type,
                },
                {
                    "type": "text",
                    "text": (
                        f"{direction_text}\n"
                        f"Maintain visual identity and branding consistent with the reference image."
                    ),
                },
            ]
        else:
            input_payload = direction_text

        # 1. Initiate interaction via async client
        try:
            interaction = await self.client.aio.interactions.create(
                model=self.model,
                input=input_payload,
            )
        except Exception as e:
            logger.error(f"Gemini Interactions API request failed: {e}")
            raise RuntimeError(f"Gemini Omni Flash generation failed: {e}") from e

        # 2. Poll for completion if interaction is asynchronous / in-progress
        interaction_id = getattr(interaction, "id", None)
        status = getattr(interaction, "status", None)
        elapsed = 0.0

        while status in ("in_progress", "queued") and interaction_id:
            if elapsed >= self.timeout:
                raise TimeoutError(
                    f"Gemini Omni Flash generation timed out after {self.timeout}s "
                    f"(Interaction ID: {interaction_id})"
                )
            logger.info(
                f"Interaction {interaction_id} status is '{status}'. Polling in {self.poll_interval}s..."
            )
            await asyncio.sleep(self.poll_interval)
            elapsed += self.poll_interval

            interaction = await self.client.aio.interactions.get(id=interaction_id)
            status = getattr(interaction, "status", None)

        if status in ("failed", "cancelled", "budget_exceeded"):
            errors = getattr(interaction, "errors", None)
            raise RuntimeError(
                f"Gemini Omni Flash interaction {interaction_id} terminated with status '{status}': {errors}"
            )

        # 3. Extract video bytes or download from URI
        video_bytes = await self._extract_video_bytes(interaction)

        if not video_bytes:
            raise RuntimeError(
                f"Gemini Omni Flash interaction completed but did not return video data or URI. "
                f"Attributes: {dir(interaction)}"
            )

        dest.write_bytes(video_bytes)
        logger.info(f"Successfully saved video clip to {dest} ({len(video_bytes)} bytes)")
        return str(dest)

    async def _extract_video_bytes(self, interaction: Any) -> bytes | None:
        """Extract binary video bytes from interaction object or remote URI."""
        # 1. Check top-level output_video property
        if hasattr(interaction, "output_video") and interaction.output_video:
            out_vid = interaction.output_video
            data = await self._resolve_video_item(out_vid)
            if data:
                return data

        # 2. Check steps (standard model_output format)
        steps = getattr(interaction, "steps", None)
        if isinstance(steps, list):
            for step in reversed(steps):
                step_type = getattr(step, "type", None) or (step.get("type") if isinstance(step, dict) else None)
                if step_type == "model_output":
                    content = getattr(step, "content", None) or (step.get("content") if isinstance(step, dict) else None)
                    if isinstance(content, list):
                        for item in reversed(content):
                            item_type = getattr(item, "type", None) or (item.get("type") if isinstance(item, dict) else None)
                            if item_type == "video":
                                data = await self._resolve_video_item(item)
                                if data:
                                    return data

        # 3. Check legacy outputs property
        outputs = getattr(interaction, "outputs", None)
        if isinstance(outputs, list):
            for item in reversed(outputs):
                item_type = getattr(item, "type", None) or (item.get("type") if isinstance(item, dict) else None)
                if item_type == "video" or hasattr(item, "video"):
                    data = await self._resolve_video_item(item)
                    if data:
                        return data

        # 4. Fallback: check candidates (generate_content format)
        candidates = getattr(interaction, "candidates", None)
        if isinstance(candidates, list) and candidates:
            parts = getattr(candidates[0].content, "parts", [])
            for part in parts:
                inline = getattr(part, "inline_data", None)
                if inline and getattr(inline, "data", None):
                    raw = inline.data
                    return base64.b64decode(raw) if isinstance(raw, str) else raw

        return None

    async def _resolve_video_item(self, item: Any) -> bytes | None:
        """Resolve a video content item into raw bytes from either inline data or URI."""
        data = getattr(item, "data", None) or (item.get("data") if isinstance(item, dict) else None)
        if data:
            if isinstance(data, str):
                return base64.b64decode(data)
            if isinstance(data, bytes):
                return data

        raw_bytes = getattr(item, "bytes", None) or (item.get("bytes") if isinstance(item, dict) else None)
        if raw_bytes and isinstance(raw_bytes, bytes):
            return raw_bytes

        uri = getattr(item, "uri", None) or (item.get("uri") if isinstance(item, dict) else None)
        if uri and isinstance(uri, str):
            logger.info(f"Downloading video from remote URI: {uri[:80]}...")
            if uri.startswith(("http://", "https://")):
                async with httpx.AsyncClient(timeout=120.0) as http_client:
                    res = await http_client.get(uri)
                    res.raise_for_status()
                    return res.content
            # Google File URI download
            try:
                downloaded = await asyncio.to_thread(self.client.files.download, file=uri)
                if downloaded:
                    return downloaded
            except Exception as e:
                logger.warning(f"client.files.download failed for {uri}: {e}")

        return None
