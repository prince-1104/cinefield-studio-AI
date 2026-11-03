"""Registry for video generation providers and models."""

from typing import Any
from app.services.video_providers.base import BaseVideoProvider, VideoModelInfo
from app.services.video_providers.seedance_provider import SeedanceVideoProvider
from app.services.video_providers.gemini_provider import GeminiVideoProvider


class VideoProviderRegistry:
    """Central registry for discovering, selecting, and delegating to video providers."""

    def __init__(self) -> None:
        self._providers: dict[str, BaseVideoProvider] = {}
        # Register standard providers
        self.register_provider(SeedanceVideoProvider())
        self.register_provider(GeminiVideoProvider())

    def register_provider(self, provider: BaseVideoProvider) -> None:
        """Register a video provider instance."""
        self._providers[provider.provider_id] = provider

    def get_provider(self, provider_id: str) -> BaseVideoProvider:
        """Get provider by key ('seedance', 'gemini'). Raises KeyError if not found."""
        if provider_id not in self._providers:
            raise KeyError(f"Video provider '{provider_id}' is not registered. Available: {list(self._providers.keys())}")
        return self._providers[provider_id]

    def list_available_models(self) -> list[VideoModelInfo]:
        """Aggregate available models from all registered providers."""
        all_models: list[VideoModelInfo] = []
        for provider in self._providers.values():
            all_models.extend(provider.get_models())
        return all_models

    def get_provider_for_model(self, model_id: str) -> tuple[BaseVideoProvider, VideoModelInfo]:
        """Find the provider and model metadata for a given model identifier."""
        for provider in self._providers.values():
            for m in provider.get_models():
                if m.id == model_id:
                    return provider, m
        # If not an exact model ID match, check if it's a Seedance endpoint ID (ep-...) or fallback to Seedance
        if model_id.startswith("ep-") or "seedance" in model_id.lower():
            seedance = self.get_provider("seedance")
            return seedance, seedance.get_models()[0]
        # Default fallback
        seedance = self.get_provider("seedance")
        return seedance, seedance.get_models()[0]


# Global singleton instance
provider_registry = VideoProviderRegistry()

