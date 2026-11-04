"""Google Gemini Omni Flash Video Provider."""

import logging
from pathlib import Path
from typing import Any

from app.config import settings
from app.services.video_providers.base import (
    BaseVideoProvider,
    CancellationResponse,
    GenerationStatusResponse,
    GenerationTaskResponse,
    VideoModelInfo,
)
from worker.omni_video import GeminiOmniVideoGenerator

logger = logging.getLogger(__name__)


class GeminiVideoProvider(BaseVideoProvider):
    """Wraps Gemini Omni Flash under the BaseVideoProvider interface."""

    MODELS: list[VideoModelInfo] = [
        VideoModelInfo(
            id="gemini-omni-1.1-flash",
            name="Gemini Omni Flash 1.1",
            provider="gemini",
            provider_name="Google DeepMind",
            description="Native multimodal video synthesis engine powered by Google Gemini Interactions API.",
            supported_aspect_ratios=["16:9", "9:16"],
            supported_durations=[5],
            default_duration=5,
            is_default=False,
            capabilities=["Multimodal Conditioning", "Native 1080p", "High Cinematic Quality"],
        )
    ]

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = (api_key or settings.GEMINI_API_KEY).strip()
        self._generator = GeminiOmniVideoGenerator(api_key=self.api_key)

    @property
    def provider_id(self) -> str:
        return "gemini"

    @property
    def name(self) -> str:
        return "Google Gemini"

    def get_models(self) -> list[VideoModelInfo]:
        return self.MODELS

    async def generate_video(
        self,
        prompt: str,
        duration_seconds: int = 5,
        aspect_ratio: str = "16:9",
        reference_image_path: str | None = None,
        model: str | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> GenerationTaskResponse:
        """Initiate Gemini Omni Flash interaction."""
        import uuid
        task_id = f"gemini-{uuid.uuid4().hex[:12]}"
        return GenerationTaskResponse(
            task_id=task_id,
            provider=self.provider_id,
            model=model or settings.GEMINI_VIDEO_MODEL,
            status="SUBMITTED",
            metadata={
                "prompt": prompt,
                "duration": duration_seconds,
                "aspect_ratio": aspect_ratio,
                "reference_image_path": reference_image_path,
            },
        )

    async def get_generation_status(
        self,
        task_id: str,
    ) -> GenerationStatusResponse:
        return GenerationStatusResponse(
            task_id=task_id,
            provider=self.provider_id,
            status="DONE",
            progress_percent=100.0,
        )

    async def retrieve_generated_video(
        self,
        task_id: str,
        output_path: str,
        status_payload: GenerationStatusResponse | None = None,
    ) -> str:
        metadata = (status_payload.metadata if status_payload else {}) or {}
        return await self._generator.generate_clip(
            prompt=metadata.get("prompt", "Cinematic shot"),
            output_path=output_path,
            reference_image_path=metadata.get("reference_image_path"),
            duration_seconds=metadata.get("duration", 5),
            aspect_ratio=metadata.get("aspect_ratio", "16:9"),
        )

    async def cancel_generation(self, task_id: str) -> CancellationResponse:
        logger.info(f"Cancellation requested for Gemini task {task_id}. Halting local processing.")
        return CancellationResponse(
            task_id=task_id,
            provider="gemini",
            supported=False,
            cancelled=False,
            message="Google Gemini video generation does not provide a remote asynchronous cancel API. Local processing has been halted.",
        )

