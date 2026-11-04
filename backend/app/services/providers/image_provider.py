"""Image generation provider adapter (DALL-E 3)."""

import logging
from pathlib import Path
from typing import Any
import httpx

from app.config import settings
from app.services.providers.base import (
    BaseProvider,
    ModelCapability,
    ModelParameter,
    ModelSpec,
)

logger = logging.getLogger(__name__)


class ImageProvider(BaseProvider):
    """Integrates with image generation models (DALL-E 3) for reference art and style frames."""

    MODELS = [
        ModelSpec(
            id="dall-e-3",
            name="OpenAI DALL-E 3",
            provider="openai",
            provider_name="OpenAI",
            capability=ModelCapability.IMAGE_GENERATION.value,
            description="Leading image synthesis model for photorealistic product concept shots and creative reference keyframes.",
            supported_aspect_ratios=["16:9", "1:1", "9:16"],
            supported_parameters=[
                ModelParameter.ASPECT_RATIO.value,
                ModelParameter.RESOLUTION.value,
                ModelParameter.STYLE.value,
            ],
            capabilities_badges=["HD Resolution", "Prompt Adherence", "Photorealistic"],
            is_default=True,
            pricing_unit="images",
            pricing_summary={"price_per_hd_image": 0.08, "price_per_std_image": 0.04},
        ),
    ]

    def __init__(self, api_key: str | None = None) -> None:
        self.api_key = (api_key if api_key is not None else getattr(settings, "OPENAI_API_KEY", "")).strip()

    @property
    def provider_id(self) -> str:
        return "openai_image"

    @property
    def name(self) -> str:
        return "OpenAI Image (DALL-E)"

    @property
    def supported_capabilities(self) -> list[ModelCapability]:
        return [ModelCapability.IMAGE_GENERATION]

    def validate_credentials(self) -> tuple[bool, str | None]:
        if not self.api_key:
            return False, "OPENAI_API_KEY environment variable is not configured."
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

    async def generate_image(
        self,
        prompt: str,
        output_path: str,
        model: str | None = None,
        aspect_ratio: str = "16:9",
    ) -> str:
        is_configured, reason = self.validate_credentials()
        if not is_configured:
            raise RuntimeError(reason)

        resolved_model = model or "dall-e-3"
        size = "1792x1024" if aspect_ratio in ("16:9", "landscape") else "1024x1792" if aspect_ratio in ("9:16", "portrait") else "1024x1024"

        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": resolved_model,
            "prompt": prompt,
            "size": size,
            "quality": "hd",
            "n": 1,
        }

        dest = Path(output_path).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)

        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post("https://api.openai.com/v1/images/generations", json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            image_url = data["data"][0]["url"]

            img_resp = await client.get(image_url)
            img_resp.raise_for_status()
            dest.write_bytes(img_resp.content)

        return str(dest)
