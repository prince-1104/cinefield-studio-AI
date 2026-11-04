"""ByteDance Seedance Video Generation Provider via BytePlus ModelArk API."""

import asyncio
import base64
import logging
import mimetypes
from pathlib import Path
from typing import Any

import httpx

from app.config import settings
from app.services.providers.base import (
    BaseProvider,
    GenerationStatusResponse,
    GenerationTaskResponse,
    ModelCapability,
    ModelParameter,
    ModelSpec,
)

logger = logging.getLogger(__name__)


class SeedanceProvider(BaseProvider):
    """Integrates with ByteDance Seedance Video Foundation models."""

    MODELS = [
        ModelSpec(
            id="dreamina-seedance-2-5-260628",
            name="Seedance 2.5 Industrial",
            provider="seedance",
            provider_name="ByteDance Seedance",
            capability=ModelCapability.VIDEO_GENERATION.value,
            description="Flagship industrial-grade video foundation model with 30s generation, advanced camera physics, and multi-modal continuity.",
            supported_aspect_ratios=["16:9", "9:16", "1:1", "4:3", "3:4", "21:9"],
            supported_durations=[5, 10, 15, 30],
            default_duration=5,
            supported_parameters=[
                ModelParameter.DURATION.value,
                ModelParameter.ASPECT_RATIO.value,
                ModelParameter.RESOLUTION.value,
                ModelParameter.REFERENCE_IMAGES.value,
            ],
            capabilities_badges=[
                "Native 1080p",
                "Up to 30s Generation",
                "First-Frame Conditioning",
                "Camera Motion Physics",
                "High Frame Coherence",
            ],
            is_default=True,
            pricing_unit="video_seconds",
            pricing_summary={"price_per_second": 0.05, "price_per_minute": 3.00},
        ),
        ModelSpec(
            id="seedance-1-0-pro-250528",
            name="Seedance 1.0 Pro",
            provider="seedance",
            provider_name="ByteDance Seedance",
            capability=ModelCapability.VIDEO_GENERATION.value,
            description="Cinematic video synthesis with advanced temporal consistency and dynamic camera movement.",
            supported_aspect_ratios=["16:9", "9:16"],
            supported_durations=[5, 10],
            default_duration=5,
            supported_parameters=[
                ModelParameter.DURATION.value,
                ModelParameter.ASPECT_RATIO.value,
                ModelParameter.REFERENCE_IMAGES.value,
            ],
            capabilities_badges=["1080p Resolution", "First-Frame Image", "Camera Control"],
            is_default=False,
            pricing_unit="video_seconds",
            pricing_summary={"price_per_second": 0.035, "price_per_minute": 2.10},
        ),
        ModelSpec(
            id="seedance-1-0-pro-fast-251015",
            name="Seedance 1.0 Pro Fast",
            provider="seedance",
            provider_name="ByteDance Seedance",
            capability=ModelCapability.VIDEO_GENERATION.value,
            description="High-throughput fast video generation optimized for rapid creative storyboarding.",
            supported_aspect_ratios=["16:9", "9:16"],
            supported_durations=[5, 10],
            default_duration=5,
            supported_parameters=[
                ModelParameter.DURATION.value,
                ModelParameter.ASPECT_RATIO.value,
            ],
            capabilities_badges=["Rapid Generation", "1080p Resolution"],
            is_default=False,
            pricing_unit="video_seconds",
            pricing_summary={"price_per_second": 0.025, "price_per_minute": 1.50},
        ),
    ]

    def __init__(
        self,
        api_key: str | None = None,
        resource_id: str | None = None,
        base_url: str | None = None,
        default_model: str | None = None,
    ) -> None:
        self.api_key = (api_key if api_key is not None else getattr(settings, "SEEDANCE_API_KEY", "")).strip()
        self.resource_id = (resource_id if resource_id is not None else getattr(settings, "SEEDANCE_RESOURCE_ID", "")).strip()
        self.base_url = (base_url or getattr(settings, "SEEDANCE_BASE_URL", "https://ark.ap-southeast.bytepluses.com/api/v3")).rstrip("/")
        self.default_model = (default_model or getattr(settings, "SEEDANCE_DEFAULT_MODEL", "dreamina-seedance-2-5-260628")).strip()

    @property
    def provider_id(self) -> str:
        return "seedance"

    @property
    def name(self) -> str:
        return "ByteDance Seedance"

    @property
    def supported_capabilities(self) -> list[ModelCapability]:
        return [ModelCapability.VIDEO_GENERATION]

    def validate_credentials(self) -> tuple[bool, str | None]:
        """Validate if SEEDANCE_API_KEY is configured."""
        if not self.api_key:
            return False, "SEEDANCE_API_KEY environment variable is not configured."
        return True, None

    def get_models(self) -> list[ModelSpec]:
        """Return all supported Seedance models with dynamic availability."""
        is_configured, reason = self.validate_credentials()
        configured_default = self.default_model or "dreamina-seedance-2-5-260628"
        known_ids = {m.id for m in self.MODELS}

        specs: list[ModelSpec] = []
        for m in self.MODELS:
            spec = m.model_copy()
            spec.is_default = (spec.id == configured_default)
            spec.is_available = is_configured
            spec.unavailability_reason = reason
            specs.append(spec)

        # Support custom endpoint if configured
        if configured_default and configured_default not in known_ids:
            specs.insert(
                0,
                ModelSpec(
                    id=configured_default,
                    name=f"Custom Seedance Endpoint ({configured_default[:16]})",
                    provider=self.provider_id,
                    provider_name=self.name,
                    capability=ModelCapability.VIDEO_GENERATION.value,
                    description=f"Custom Seedance ModelArk endpoint: {configured_default}",
                    supported_aspect_ratios=["16:9", "9:16", "1:1"],
                    supported_durations=[5, 10, 15, 30],
                    default_duration=5,
                    supported_parameters=[
                        ModelParameter.DURATION.value,
                        ModelParameter.ASPECT_RATIO.value,
                    ],
                    capabilities_badges=["Custom ModelArk Endpoint"],
                    is_default=True,
                    is_available=is_configured,
                    unavailability_reason=reason,
                    pricing_unit="video_seconds",
                    pricing_summary={"price_per_second": 0.05},
                ),
            )
        return specs

    def _get_headers(self) -> dict[str, str]:
        is_configured, reason = self.validate_credentials()
        if not is_configured:
            raise RuntimeError(reason)
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.resource_id:
            headers["X-Resource-Id"] = self.resource_id
        return headers

    def _resolve_model_id(self, requested_model: str | None) -> str:
        if requested_model:
            return requested_model
        if self.resource_id and self.resource_id.startswith("ep-"):
            return self.resource_id
        return self.default_model or "dreamina-seedance-2-5-260628"

    async def generate_video(
        self,
        prompt: str,
        duration_seconds: int = 5,
        aspect_ratio: str = "16:9",
        reference_image_path: str | None = None,
        model: str | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> GenerationTaskResponse:
        resolved_model = self._resolve_model_id(model)
        headers = self._get_headers()

        content: list[dict[str, Any]] = [{"type": "text", "text": prompt}]

        if reference_image_path and Path(reference_image_path).is_file():
            ref_path = Path(reference_image_path)
            mime_type, _ = mimetypes.guess_type(str(ref_path))
            mime_type = mime_type or "image/png"
            b64_data = base64.b64encode(ref_path.read_bytes()).decode("utf-8")
            content.append({
                "type": "image_url",
                "image_url": {"url": f"data:{mime_type};base64,{b64_data}"},
                "role": "first_frame",
            })

        formatted_ratio = "16:9" if aspect_ratio in ("16:9", "landscape") else "9:16"
        valid_duration = 5
        if duration_seconds >= 25:
            valid_duration = 30
        elif duration_seconds >= 12:
            valid_duration = 15
        elif duration_seconds >= 8:
            valid_duration = 10

        payload: dict[str, Any] = {
            "model": resolved_model,
            "content": content,
            "resolution": "1080p",
            "ratio": formatted_ratio,
            "duration": valid_duration,
        }

        # Apply supported optional parameters only
        if parameters:
            for k in ("seed", "camera_motion", "motion_level"):
                if k in parameters:
                    payload[k] = parameters[k]

        endpoint = f"{self.base_url}/contents/generations/tasks"
        logger.info(f"Submitting Seedance video task to {endpoint} with model {resolved_model}")

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post(endpoint, json=payload, headers=headers)
            if resp.status_code >= 400:
                raise RuntimeError(f"Seedance API error ({resp.status_code}): {resp.text}")
            data = resp.json()
            task_id = data.get("id") or (data.get("data") or {}).get("task_id") or ""
            if not task_id:
                raise RuntimeError(f"Seedance response did not contain task_id: {data}")
            return GenerationTaskResponse(
                task_id=task_id,
                provider=self.provider_id,
                model=resolved_model,
                status="SUBMITTED",
                metadata={"duration": valid_duration, "ratio": formatted_ratio},
            )

    async def get_generation_status(self, task_id: str) -> GenerationStatusResponse:
        headers = self._get_headers()
        endpoint = f"{self.base_url}/contents/generations/tasks/{task_id}"

        async with httpx.AsyncClient(timeout=30.0) as client:
            resp = await client.get(endpoint, headers=headers)
            if resp.status_code >= 400:
                return GenerationStatusResponse(
                    task_id=task_id,
                    provider=self.provider_id,
                    status="FAILED",
                    error_message=f"HTTP {resp.status_code}: {resp.text}",
                )
            data = resp.json()
            root = data.get("data") or data
            raw_status = (root.get("status") or "").upper()
            status = "QUEUED"
            if raw_status in ("SUCCESS", "SUCCEEDED", "DONE", "COMPLETED"):
                status = "DONE"
            elif raw_status in ("RUNNING", "PROCESSING", "GENERATING"):
                status = "RUNNING"
            elif raw_status in ("FAILED", "FAIL", "ERROR", "CANCELED"):
                status = "FAILED"

            video_url = None
            if status == "DONE":
                content = root.get("content") or {}
                video_url = content.get("video_url") or root.get("video_url")

            error_msg = None
            if status == "FAILED":
                error_msg = (root.get("error") or {}).get("message") or root.get("message") or "Seedance generation failed"

            return GenerationStatusResponse(
                task_id=task_id,
                provider=self.provider_id,
                status=status,
                video_url=video_url,
                error_message=error_msg,
                metadata=root,
            )

    async def retrieve_generated_video(
        self,
        task_id: str,
        output_path: str,
        status_payload: GenerationStatusResponse | None = None,
    ) -> str:
        video_url = None
        if status_payload and status_payload.video_url:
            video_url = status_payload.video_url
        else:
            status = await self.get_generation_status(task_id)
            video_url = status.video_url

        if not video_url:
            raise RuntimeError(f"No video download URL available for task {task_id}")

        out_file = Path(output_path)
        out_file.parent.mkdir(parents=True, exist_ok=True)

        async with httpx.AsyncClient(timeout=180.0, follow_redirects=True) as client:
            resp = await client.get(video_url)
            resp.raise_for_status()
            out_file.write_bytes(resp.content)

        return str(out_file)

