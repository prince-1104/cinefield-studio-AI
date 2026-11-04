"""Google Gemini Video and Text Provider Adapter."""

import logging
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


class GeminiProvider(BaseProvider):
    """Integrates with Google Gemini for omni multimodal video and text planning."""

    MODELS = [
        ModelSpec(
            id="gemini-omni-1.1-flash",
            name="Gemini Omni 1.1 Flash",
            provider="gemini",
            provider_name="Google Gemini",
            capability=ModelCapability.VIDEO_GENERATION.value,
            description="Ultra-fast Google multimodal foundation video synthesis engine.",
            supported_aspect_ratios=["16:9", "9:16"],
            supported_durations=[5, 10],
            default_duration=5,
            supported_parameters=[
                ModelParameter.DURATION.value,
                ModelParameter.ASPECT_RATIO.value,
            ],
            capabilities_badges=["Flash Speed", "720p/1080p Resolution"],
            is_default=False,
            pricing_unit="video_seconds",
            pricing_summary={"price_per_second": 0.02, "price_per_minute": 1.20},
        ),
        ModelSpec(
            id="gemini-3.8-flash",
            name="Gemini 3.8 Flash",
            provider="gemini",
            provider_name="Google Gemini",
            capability=ModelCapability.TEXT_GENERATION.value,
            description="High-velocity multimodal reasoning model for rapid script iteration and taglines.",
            supported_parameters=[
                ModelParameter.TEMPERATURE.value,
            ],
            capabilities_badges=["High Velocity", "Multimodal Context"],
            is_default=False,
            pricing_unit="tokens",
            pricing_summary={"input_per_million": 0.075, "output_per_million": 0.30},
        ),
    ]

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = (api_key if api_key is not None else getattr(settings, "GEMINI_API_KEY", "")).strip()

    @property
    def provider_id(self) -> str:
        return "gemini"

    @property
    def name(self) -> str:
        return "Google Gemini"

    @property
    def supported_capabilities(self) -> list[ModelCapability]:
        return [ModelCapability.VIDEO_GENERATION, ModelCapability.TEXT_GENERATION]

    def validate_credentials(self) -> tuple[bool, str | None]:
        if not self.api_key:
            return False, "GEMINI_API_KEY environment variable is not configured."
        return True, None

    def get_models(self) -> list[ModelSpec]:
        is_configured, reason = self.validate_credentials()
        specs: list[ModelSpec] = []
        for m in self.MODELS:
            spec = m.model_copy()
            spec.is_available = is_configured
            spec.unavailability_reason = reason
            specs.append(spec)
        return specs

    async def generate_video(
        self,
        prompt: str,
        duration_seconds: int = 5,
        aspect_ratio: str = "16:9",
        reference_image_path: str | None = None,
        model: str | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> GenerationTaskResponse:
        is_configured, reason = self.validate_credentials()
        if not is_configured:
            raise RuntimeError(reason)
        # Gemini mock / synchronous generation hook
        resolved_model = model or "gemini-omni-1.1-flash"
        return GenerationTaskResponse(
            task_id=f"gemini_task_{int(duration_seconds)}s",
            provider=self.provider_id,
            model=resolved_model,
            status="DONE",
            metadata={"duration": duration_seconds, "ratio": aspect_ratio},
        )

