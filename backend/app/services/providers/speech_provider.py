"""OpenAI Speech / Text-to-Speech provider adapter."""

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


class SpeechProvider(BaseProvider):
    """Integrates with OpenAI Text-to-Speech API for voiceovers and narration."""

    MODELS = [
        ModelSpec(
            id="gpt-4o-mini-tts",
            name="OpenAI Expressive TTS (gpt-4o-mini-tts)",
            provider="openai",
            provider_name="OpenAI",
            capability=ModelCapability.SPEECH_GENERATION.value,
            description="Expressive text-to-speech model supporting stylistic direction, tone modulation, and cinematic pacing.",
            supported_parameters=[
                ModelParameter.VOICE.value,
                ModelParameter.AUDIO.value,
            ],
            capabilities_badges=["Expressive Modulation", "Multiple Voices", "MP3 Output"],
            is_default=True,
            pricing_unit="tokens",
            pricing_summary={"input_per_million": 0.15, "output_per_million": 0.60},
        ),
        ModelSpec(
            id="tts-1",
            name="OpenAI TTS-1 Standard",
            provider="openai",
            provider_name="OpenAI",
            capability=ModelCapability.SPEECH_GENERATION.value,
            description="Standard low-latency text-to-speech engine optimized for real-time streaming audio.",
            supported_parameters=[
                ModelParameter.VOICE.value,
            ],
            capabilities_badges=["Low Latency", "Clear Narration"],
            is_default=False,
            pricing_unit="characters",
            pricing_summary={"price_per_1k_chars": 0.015},
        ),
        ModelSpec(
            id="tts-1-hd",
            name="OpenAI TTS-1 HD",
            provider="openai",
            provider_name="OpenAI",
            capability=ModelCapability.SPEECH_GENERATION.value,
            description="High-definition studio quality text-to-speech engine for broadcast and master advertisements.",
            supported_parameters=[
                ModelParameter.VOICE.value,
            ],
            capabilities_badges=["High Definition", "Studio Quality"],
            is_default=False,
            pricing_unit="characters",
            pricing_summary={"price_per_1k_chars": 0.030},
        ),
    ]

    def __init__(self, api_key: str | None = None, default_model: str | None = None) -> None:
        self.api_key = (api_key if api_key is not None else getattr(settings, "OPENAI_API_KEY", "")).strip()
        self.default_model = (default_model or getattr(settings, "OPENAI_TTS_MODEL", "gpt-4o-mini-tts")).strip()

    @property
    def provider_id(self) -> str:
        return "openai"

    @property
    def name(self) -> str:
        return "OpenAI Speech"

    @property
    def supported_capabilities(self) -> list[ModelCapability]:
        return [ModelCapability.SPEECH_GENERATION]

    def validate_credentials(self) -> tuple[bool, str | None]:
        """Validate if OPENAI_API_KEY is configured."""
        if not self.api_key:
            return False, "OPENAI_API_KEY environment variable is not configured."
        return True, None

    def get_models(self) -> list[ModelSpec]:
        is_configured, reason = self.validate_credentials()
        configured_default = self.default_model or "gpt-4o-mini-tts"

        specs: list[ModelSpec] = []
        for m in self.MODELS:
            spec = m.model_copy()
            spec.is_default = (spec.id == configured_default)
            spec.is_available = is_configured
            spec.unavailability_reason = reason
            specs.append(spec)
        return specs

    async def generate_speech(
        self,
        text: str,
        output_path: str,
        model: str | None = None,
        voice: str = "coral",
    ) -> str:
        is_configured, reason = self.validate_credentials()
        if not is_configured:
            raise RuntimeError(reason)

        resolved_model = model or self.default_model or "gpt-4o-mini-tts"
        headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json",
        }
        payload = {
            "model": resolved_model,
            "input": text,
            "voice": voice,
            "response_format": "mp3",
        }

        dest = Path(output_path).resolve()
        dest.parent.mkdir(parents=True, exist_ok=True)

        async with httpx.AsyncClient(timeout=60.0) as client:
            resp = await client.post("https://api.openai.com/v1/audio/speech", json=payload, headers=headers)
            resp.raise_for_status()
            dest.write_bytes(resp.content)

        return str(dest)
