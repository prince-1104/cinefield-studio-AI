"""Anthropic Claude LLM Provider for Creative Direction and Storyboard Planning."""

import logging
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


class ClaudeProvider(BaseProvider):
    """Integrates with Anthropic Claude for creative brief & storyboard planning."""

    MODELS = [
        ModelSpec(
            id="claude-3-7-sonnet-20250219",
            name="Claude 3.7 Sonnet (Hybrid Reasoning)",
            provider="claude",
            provider_name="Anthropic Claude",
            capability=ModelCapability.TEXT_GENERATION.value,
            description="State-of-the-art hybrid reasoning model for cinematic creative direction, visual continuity, and complex storyboard planning.",
            supported_parameters=[
                ModelParameter.TEMPERATURE.value,
            ],
            capabilities_badges=["Extended Thinking", "Complex Tool Use", "Cinematic Arc Planning"],
            is_default=True,
            pricing_unit="tokens",
            pricing_summary={"input_per_million": 3.00, "output_per_million": 15.00},
        ),
        ModelSpec(
            id="claude-3-5-sonnet-20241022",
            name="Claude 3.5 Sonnet",
            provider="claude",
            provider_name="Anthropic Claude",
            capability=ModelCapability.TEXT_GENERATION.value,
            description="High-intelligence flagship model with exceptional creative writing and nuanced narrative structuring.",
            supported_parameters=[
                ModelParameter.TEMPERATURE.value,
            ],
            capabilities_badges=["High Intelligence", "Structured Tool Use", "Fast"],
            is_default=False,
            pricing_unit="tokens",
            pricing_summary={"input_per_million": 3.00, "output_per_million": 15.00},
        ),
        ModelSpec(
            id="claude-3-5-haiku-20241022",
            name="Claude 3.5 Haiku",
            provider="claude",
            provider_name="Anthropic Claude",
            capability=ModelCapability.TEXT_GENERATION.value,
            description="Fastest, lightweight intelligence optimized for rapid taglines, short copy variants, and micro adjustments.",
            supported_parameters=[
                ModelParameter.TEMPERATURE.value,
            ],
            capabilities_badges=["Ultra Fast", "Cost Efficient"],
            is_default=False,
            pricing_unit="tokens",
            pricing_summary={"input_per_million": 0.80, "output_per_million": 4.00},
        ),
    ]

    def __init__(self, api_key: str | None = None, default_model: str | None = None) -> None:
        self.api_key = (api_key if api_key is not None else getattr(settings, "CLAUDE_API_KEY", "")).strip()
        self.default_model = (default_model or getattr(settings, "CLAUDE_MODEL", "claude-3-7-sonnet-20250219")).strip()

    @property
    def provider_id(self) -> str:
        return "claude"

    @property
    def name(self) -> str:
        return "Anthropic Claude"

    @property
    def supported_capabilities(self) -> list[ModelCapability]:
        return [ModelCapability.TEXT_GENERATION]

    def validate_credentials(self) -> tuple[bool, str | None]:
        """Validate if CLAUDE_API_KEY is configured."""
        if not self.api_key:
            return False, "CLAUDE_API_KEY environment variable is not configured."
        return True, None

    def get_models(self) -> list[ModelSpec]:
        is_configured, reason = self.validate_credentials()
        configured_default = self.default_model or "claude-3-7-sonnet-20250219"

        specs: list[ModelSpec] = []
        for m in self.MODELS:
            spec = m.model_copy()
            spec.is_default = (spec.id == configured_default)
            spec.is_available = is_configured
            spec.unavailability_reason = reason
            specs.append(spec)
        return specs

    async def generate_text(
        self,
        prompt: str,
        system_instruction: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        is_configured, reason = self.validate_credentials()
        if not is_configured:
            raise RuntimeError(reason)

        resolved_model = model or self.default_model or "claude-3-7-sonnet-20250219"
        headers = {
            "x-api-key": self.api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        }

        payload: dict[str, Any] = {
            "model": resolved_model,
            "max_tokens": max_tokens,
            "messages": [{"role": "user", "content": prompt}],
        }
        if system_instruction:
            payload["system"] = system_instruction
        if temperature is not None:
            payload["temperature"] = temperature
        if tools:
            payload["tools"] = tools

        async with httpx.AsyncClient(timeout=90.0) as client:
            resp = await client.post("https://api.anthropic.com/v1/messages", json=payload, headers=headers)
            resp.raise_for_status()
            return resp.json()
