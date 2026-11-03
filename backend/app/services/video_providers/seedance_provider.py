"""ByteDance Seedance Video Generation Provider via BytePlus / Volcengine ModelArk API."""

import asyncio
import base64
import logging
import mimetypes
from pathlib import Path
from typing import Any

import httpx

from app.config import settings
from app.services.video_providers.base import (
    BaseVideoProvider,
    GenerationStatusResponse,
    GenerationTaskResponse,
    VideoModelInfo,
)

logger = logging.getLogger(__name__)


class SeedanceVideoProvider(BaseVideoProvider):
    """Integrates with ByteDance Seedance Video Generation models via ModelArk."""

    MODELS: list[VideoModelInfo] = [
        VideoModelInfo(
            id="dreamina-seedance-2-5-260628",
            name="Seedance 2.5 Industrial",
            provider="seedance",
            provider_name="ByteDance Seedance",
            description="Latest flagship industrial-grade video foundation model with 30s generation, advanced multimodal conditioning, and camera motion physics.",
            supported_aspect_ratios=["16:9", "9:16", "1:1", "4:3", "3:4", "21:9"],
            supported_durations=[5, 10, 15, 30],
            default_duration=5,
            is_default=True,
            capabilities=[
                "Native 1080p Resolution",
                "Long-Form Up to 30s",
                "Advanced Reference Image Conditioning",
                "Cinematic Camera Motion",
                "High Frame Stability",
            ],
        ),
        VideoModelInfo(
            id="seedance-1-0-pro-250528",
            name="Seedance 1.0 Pro",
            provider="seedance",
            provider_name="ByteDance Seedance",
            description="Flagship cinematic video generator with advanced temporal coherence and motion physics.",
            supported_aspect_ratios=["16:9", "9:16"],
            supported_durations=[5, 10],
            default_duration=5,
            is_default=False,
            capabilities=["1080p Resolution", "First-Frame Image Conditioning", "Camera Motion Control"],
        ),
        VideoModelInfo(
            id="seedance-1-0-pro-fast-251015",
            name="Seedance 1.0 Pro Fast",
            provider="seedance",
            provider_name="ByteDance Seedance",
            description="High-velocity video synthesis optimized for rapid creative iteration and previews.",
            supported_aspect_ratios=["16:9", "9:16"],
            supported_durations=[5, 10],
            default_duration=5,
            is_default=False,
            capabilities=["Fast Synthesis", "1080p Resolution", "High Frame Stability"],
        ),
        VideoModelInfo(
            id="dreamina-seedance-2-0-260128",
            name="Seedance 2.0 Next-Gen",
            provider="seedance",
            provider_name="ByteDance Seedance",
            description="Next-generation multi-modal video synthesis featuring photorealistic cinematic rendering.",
            supported_aspect_ratios=["16:9", "9:16"],
            supported_durations=[5, 10],
            default_duration=5,
            is_default=False,
            capabilities=["Next-Gen Visual Dynamics", "1080p Resolution", "Multimodal Conditioning"],
        ),
    ]

    def __init__(
        self,
        api_key: str | None = None,
        resource_id: str | None = None,
        base_url: str | None = None,
        default_model: str | None = None,
        timeout_seconds: float | None = None,
    ) -> None:
        self.api_key = api_key.strip() if api_key is not None else settings.SEEDANCE_API_KEY.strip()
        self.resource_id = resource_id.strip() if resource_id is not None else settings.SEEDANCE_RESOURCE_ID.strip()
        self.base_url = (base_url if base_url is not None else settings.SEEDANCE_BASE_URL).rstrip("/")
        self.default_model = (default_model if default_model is not None else settings.SEEDANCE_DEFAULT_MODEL).strip()
        self.timeout = timeout_seconds or settings.PROVIDER_REQUEST_TIMEOUT

    @property
    def provider_id(self) -> str:
        return "seedance"

    @property
    def name(self) -> str:
        return "ByteDance Seedance"

    def get_models(self) -> list[VideoModelInfo]:
        """Return available Seedance models with is_default accurately reflecting configuration."""
        configured_default = self.default_model or settings.SEEDANCE_DEFAULT_MODEL
        known_ids = {m.id for m in self.MODELS}

        models_list: list[VideoModelInfo] = []
        for m in self.MODELS:
            models_list.append(
                VideoModelInfo(
                    id=m.id,
                    name=m.name,
                    provider=m.provider,
                    provider_name=m.provider_name,
                    description=m.description,
                    supported_aspect_ratios=m.supported_aspect_ratios,
                    supported_durations=m.supported_durations,
                    default_duration=m.default_duration,
                    is_default=(m.id == configured_default),
                    capabilities=m.capabilities,
                )
            )

        # If configured_default is a custom endpoint (e.g. ep-...) or custom ID not in MODELS, add it
        if configured_default and configured_default not in known_ids:
            models_list.insert(
                0,
                VideoModelInfo(
                    id=configured_default,
                    name=f"Custom Seedance ({configured_default[:16]})",
                    provider=self.provider_id,
                    provider_name=self.name,
                    description=f"Configured custom ModelArk model: {configured_default}",
                    supported_aspect_ratios=["16:9", "9:16", "1:1"],
                    supported_durations=[5, 10, 15, 30],
                    default_duration=5,
                    is_default=True,
                    capabilities=["ModelArk Endpoint", "Custom Inference"],
                ),
            )

        return models_list

    def _get_headers(self) -> dict[str, str]:
        if not self.api_key:
            raise RuntimeError(
                "SEEDANCE_API_KEY is not configured. "
                "Please configure a valid Seedance API key in your .env file."
            )
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
            "Accept": "application/json",
        }
        if self.resource_id:
            headers["X-Resource-Id"] = self.resource_id
        return headers

    def _resolve_model_id(self, requested_model: str | None) -> str:
        """Resolve the effective model or custom endpoint resource ID."""
        if requested_model:
            return requested_model
        # If a dedicated ModelArk endpoint ID (e.g. ep-2025...) is set as resource_id, use it
        if self.resource_id and self.resource_id.startswith("ep-"):
            return self.resource_id
        return self.default_model or settings.SEEDANCE_DEFAULT_MODEL

    async def generate_video(
        self,
        prompt: str,
        duration_seconds: int = 5,
        aspect_ratio: str = "16:9",
        reference_image_path: str | None = None,
        model: str | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> GenerationTaskResponse:
        """Submit an asynchronous video generation task to ModelArk / Seedance."""
        resolved_model = self._resolve_model_id(model)
        headers = self._get_headers()

        # Build content list
        content: list[dict[str, Any]] = [
            {
                "type": "text",
                "text": prompt,
            }
        ]

        # Image conditioning if reference image provided
        if reference_image_path and Path(reference_image_path).is_file():
            ref_path = Path(reference_image_path)
            mime_type, _ = mimetypes.guess_type(str(ref_path))
            mime_type = mime_type or "image/png"
            b64_data = base64.b64encode(ref_path.read_bytes()).decode("utf-8")
            data_uri = f"data:{mime_type};base64,{b64_data}"
            content.append({
                "type": "image_url",
                "image_url": {"url": data_uri},
                "role": "first_frame",
            })

        # Ratio formatting
        formatted_ratio = "16:9" if aspect_ratio in ("16:9", "landscape") else "9:16"
        # Seedance 2.5 supports native durations 5, 10, 15, 30
        if duration_seconds >= 25:
            valid_duration = 30
        elif duration_seconds >= 12:
            valid_duration = 15
        elif duration_seconds >= 8:
            valid_duration = 10
        else:
            valid_duration = 5

        payload: dict[str, Any] = {
            "model": resolved_model,
            "content": content,
            "resolution": "1080p",
            "ratio": formatted_ratio,
            "duration": valid_duration,
            "watermark": False,
        }

        if parameters:
            payload.update({k: v for k, v in parameters.items() if k not in payload})

        endpoint = f"{self.base_url}/contents/generations/tasks"
        logger.info(
            f"Submitting Seedance video task (model={resolved_model}, ratio={formatted_ratio}, dur={valid_duration}s)"
        )

        # Retry with exponential backoff for rate limits (429) or transient 5xx errors
        last_error: Exception | None = None
        for attempt in range(1, settings.MAX_RETRY_LIMIT + 1):
            try:
                async with httpx.AsyncClient(timeout=self.timeout) as client:
                    response = await client.post(endpoint, json=payload, headers=headers)
                    if response.status_code == 429:
                        wait_sec = 2.0 * (2 ** (attempt - 1))
                        logger.warning(
                            f"Seedance API rate limit (429) encountered. Retrying in {wait_sec}s (attempt {attempt})..."
                        )
                        await asyncio.sleep(wait_sec)
                        continue

                    response.raise_for_status()
                    data = response.json()
                    task_id = data.get("id")
                    if not task_id:
                        raise RuntimeError(f"Seedance response missing task 'id': {data}")

                    logger.info(f"Seedance task created successfully: task_id={task_id}")
                    return GenerationTaskResponse(
                        task_id=str(task_id),
                        provider=self.provider_id,
                        model=resolved_model,
                        status="SUBMITTED",
                        message="Seedance video generation task queued successfully",
                        metadata={"raw_response": data},
                    )

            except httpx.HTTPStatusError as exc:
                last_error = exc
                status_code = exc.response.status_code
                error_body = exc.response.text
                logger.error(
                    f"Seedance HTTP error {status_code}: {error_body[:200]}"
                )
                if status_code in (401, 403):
                    raise RuntimeError(
                        f"Seedance authentication failed ({status_code}). Please verify your SEEDANCE_API_KEY."
                    ) from exc
                if status_code < 500:
                    raise RuntimeError(f"Seedance API error ({status_code}): {error_body}") from exc
                await asyncio.sleep(2.0 * attempt)
            except Exception as exc:
                last_error = exc
                logger.error(f"Seedance request failed: {exc}")
                await asyncio.sleep(2.0 * attempt)

        raise RuntimeError(f"Failed to submit Seedance generation task after retries: {last_error}")

    async def get_generation_status(
        self,
        task_id: str,
    ) -> GenerationStatusResponse:
        """Poll the status of a Seedance video generation task."""
        headers = self._get_headers()
        endpoint = f"{self.base_url}/contents/generations/tasks/{task_id}"

        async with httpx.AsyncClient(timeout=self.timeout) as client:
            try:
                response = await client.get(endpoint, headers=headers)
                response.raise_for_status()
                data = response.json()
            except httpx.HTTPStatusError as exc:
                logger.error(f"Seedance status query failed for task {task_id}: {exc}")
                return GenerationStatusResponse(
                    task_id=task_id,
                    provider=self.provider_id,
                    status="FAILED",
                    error_message=f"HTTP {exc.response.status_code}: {exc.response.text}",
                )
            except Exception as exc:
                logger.error(f"Seedance status check network error for task {task_id}: {exc}")
                return GenerationStatusResponse(
                    task_id=task_id,
                    provider=self.provider_id,
                    status="RUNNING",  # Keep running on transient network failure
                    error_message=str(exc),
                )

        raw_status = (data.get("status") or "").lower()
        content = data.get("content") or {}
        video_url = None
        if isinstance(content, dict):
            video_url = content.get("video_url") or (content.get("video") or {}).get("url")
        elif isinstance(content, list) and len(content) > 0:
            first_item = content[0]
            if isinstance(first_item, dict):
                video_url = first_item.get("video_url") or (first_item.get("video") or {}).get("url")
        if not video_url:
            video_url = (data.get("video") or {}).get("url")

        if raw_status in ("succeeded", "completed"):
            return GenerationStatusResponse(
                task_id=task_id,
                provider=self.provider_id,
                status="DONE",
                progress_percent=100.0,
                video_url=video_url,
                metadata=data,
            )
        elif raw_status in ("failed", "cancelled"):
            error_info = data.get("error") or "Generation task was aborted or encountered an error"
            error_msg = error_info if isinstance(error_info, str) else error_info.get("message", str(error_info))
            return GenerationStatusResponse(
                task_id=task_id,
                provider=self.provider_id,
                status="FAILED",
                error_message=error_msg,
                metadata=data,
            )
        elif raw_status == "running":
            return GenerationStatusResponse(
                task_id=task_id,
                provider=self.provider_id,
                status="RUNNING",
                progress_percent=50.0,
                metadata=data,
            )
        else:
            # queued or other state
            return GenerationStatusResponse(
                task_id=task_id,
                provider=self.provider_id,
                status="QUEUED",
                progress_percent=10.0,
                metadata=data,
            )

    async def retrieve_generated_video(
        self,
        task_id: str,
        output_path: str,
        status_payload: GenerationStatusResponse | None = None,
    ) -> str:
        """Download the completed video stream from Seedance to local disk."""
        dest = Path(output_path).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)

        video_url = status_payload.video_url if status_payload else None
        if not video_url:
            status_resp = await self.get_generation_status(task_id)
            if status_resp.status != "DONE" or not status_resp.video_url:
                raise RuntimeError(
                    f"Cannot retrieve video for Seedance task {task_id}: task status is {status_resp.status}"
                )
            video_url = status_resp.video_url

        logger.info(f"Downloading generated Seedance video from {video_url[:80]}... to {dest.name}")

        async with httpx.AsyncClient(timeout=180.0) as client:
            async with client.stream("GET", video_url) as stream:
                stream.raise_for_status()
                with open(dest, "wb") as f:
                    async for chunk in stream.aiter_bytes(chunk_size=65536):
                        f.write(chunk)

        if not dest.is_file() or dest.stat().st_size < 1000:
            raise RuntimeError(
                f"Downloaded Seedance video at {dest} is invalid or incomplete (size: {dest.stat().st_size if dest.is_file() else 0} bytes)"
            )

        logger.info(f"Successfully saved Seedance video to {dest} ({dest.stat().st_size} bytes)")
        return str(dest)

