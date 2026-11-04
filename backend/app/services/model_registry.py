"""Central dynamic Model Registry for multi-modal AI models across providers."""

import logging
from typing import Any

from app.config import settings
from app.services.providers.base import (
    BaseProvider,
    ModelCapability,
    ModelSpec,
)
from app.services.providers.claude_provider import ClaudeProvider
from app.services.providers.seedance_provider import SeedanceProvider
from app.services.providers.speech_provider import SpeechProvider
from app.services.providers.image_provider import ImageProvider
from app.services.providers.gemini_provider import GeminiProvider

logger = logging.getLogger(__name__)


class ModelRegistry:
    """Central registry and dispatch interface for discovering, selecting, and validating AI models."""

    def __init__(self) -> None:
        self._providers: dict[str, BaseProvider] = {}
        # Register standard provider adapters
        self.register_provider(SeedanceProvider())
        self.register_provider(ClaudeProvider())
        self.register_provider(SpeechProvider())
        self.register_provider(ImageProvider())
        self.register_provider(GeminiProvider())

    def register_provider(self, provider: BaseProvider) -> None:
        """Register a provider instance."""
        self._providers[provider.provider_id] = provider

    def get_provider(self, provider_id: str) -> BaseProvider:
        """Retrieve provider adapter by identifier. Raises KeyError if not found."""
        if provider_id not in self._providers:
            raise KeyError(
                f"Provider '{provider_id}' is not registered. Registered: {list(self._providers.keys())}"
            )
        return self._providers[provider_id]

    def list_models(
        self,
        capability: str | None = None,
        include_unavailable: bool = True,
    ) -> list[ModelSpec]:
        """Aggregate models across all registered providers with dynamic availability checks.

        Args:
            capability: Optional filter by ModelCapability (e.g. 'video_generation', 'text_generation')
            include_unavailable: If False, models with missing credentials/disabled status are omitted.
        """
        all_specs: list[ModelSpec] = []
        cap_val = capability.lower() if capability else None

        for provider in self._providers.values():
            specs = provider.get_models()
            for s in specs:
                if cap_val and s.capability != cap_val:
                    continue
                if not include_unavailable and not s.is_available:
                    continue
                all_specs.append(s)

        return all_specs

    def get_model(self, model_id: str) -> ModelSpec | None:
        """Find a model specification by exact or endpoint identifier."""
        for provider in self._providers.values():
            for m in provider.get_models():
                if m.id == model_id:
                    return m
        # Check endpoint fallback
        if model_id.startswith("ep-") or "seedance" in model_id.lower():
            seedance = self.get_provider("seedance")
            models = seedance.get_models()
            return models[0] if models else None
        return None

    def get_provider_for_model(self, model_id: str) -> tuple[BaseProvider, ModelSpec]:
        """Resolve the provider and model metadata for a given model ID."""
        for provider in self._providers.values():
            for m in provider.get_models():
                if m.id == model_id:
                    return provider, m

        # Fallback to Seedance for video endpoint identifiers
        if model_id.startswith("ep-") or "seedance" in model_id.lower():
            seedance = self.get_provider("seedance")
            models = seedance.get_models()
            return seedance, models[0]

        # Default fallback to Seedance
        seedance = self.get_provider("seedance")
        return seedance, seedance.get_models()[0]

    def filter_supported_parameters(self, model_id: str, requested_params: dict[str, Any]) -> dict[str, Any]:
        """Filter out parameters that are not explicitly supported by the model specification."""
        model_spec = self.get_model(model_id)
        if not model_spec or not model_spec.supported_parameters:
            return requested_params

        supported = set(model_spec.supported_parameters)
        filtered: dict[str, Any] = {}
        for k, v in requested_params.items():
            if k in supported:
                filtered[k] = v
            else:
                logger.debug(f"Parameter '{k}' is not supported by model '{model_id}' and will not be sent.")
        return filtered


# Global singleton instance
model_registry = ModelRegistry()

