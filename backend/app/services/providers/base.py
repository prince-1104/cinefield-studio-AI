"""Base interfaces and unified data models for dynamic AI providers and model registry."""

from abc import ABC, abstractmethod
from enum import Enum
from typing import Any
from pydantic import BaseModel, Field


class ModelCapability(str, Enum):
    """Supported model modalities and operational capabilities."""

    VIDEO_GENERATION = "video_generation"
    TEXT_GENERATION = "text_generation"
    IMAGE_GENERATION = "image_generation"
    SPEECH_GENERATION = "speech_generation"
    SPEECH_TO_TEXT = "speech_to_text"


class ModelParameter(str, Enum):
    """Standardized generation parameters."""

    DURATION = "duration"
    ASPECT_RATIO = "aspect_ratio"
    RESOLUTION = "resolution"
    AUDIO = "audio"
    REFERENCE_IMAGES = "reference_images"
    NEGATIVE_PROMPT = "negative_prompt"
    VOICE = "voice"
    STYLE = "style"
    TEMPERATURE = "temperature"


class ModelSpec(BaseModel):
    """Full metadata describing any AI model across all capabilities."""

    id: str = Field(..., description="Unique model identifier used in API calls")
    name: str = Field(..., description="Human-readable model name")
    provider: str = Field(..., description="Provider machine identifier (e.g. 'seedance', 'claude')")
    provider_name: str = Field(..., description="Display name of the provider")
    capability: str = Field(..., description="Primary capability (e.g. 'video_generation', 'text_generation')")
    description: str = Field(..., description="Short summary of model capabilities and characteristics")
    supported_aspect_ratios: list[str] = Field(default_factory=list)
    supported_durations: list[int] = Field(default_factory=list)
    default_duration: int | None = None
    supported_parameters: list[str] = Field(default_factory=list)
    capabilities_badges: list[str] = Field(default_factory=list)
    is_default: bool = False
    is_available: bool = True
    unavailability_reason: str | None = None
    pricing_unit: str = "tokens"  # 'tokens', 'video_seconds', 'images', 'characters'
    pricing_summary: dict[str, Any] = Field(default_factory=dict)


class GenerationTaskResponse(BaseModel):
    """Response returned upon submitting an asynchronous generation task."""

    task_id: str
    provider: str
    model: str
    status: str  # "SUBMITTED", "RUNNING", "DONE", "FAILED"
    message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class GenerationStatusResponse(BaseModel):
    """Response returned when polling for generation progress."""

    task_id: str
    provider: str
    status: str  # "QUEUED", "RUNNING", "DONE", "FAILED"
    progress_percent: float | None = None
    video_url: str | None = None
    error_message: str | None = None
    metadata: dict[str, Any] = Field(default_factory=dict)


class BaseProvider(ABC):
    """Abstract base class for all AI providers in Pexyl Studio."""

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Machine identifier (e.g. 'seedance', 'claude', 'gemini', 'openai')."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Display name (e.g. 'ByteDance Seedance', 'Anthropic Claude')."""
        pass

    @property
    @abstractmethod
    def supported_capabilities(self) -> list[ModelCapability]:
        """List of capabilities implemented by this provider."""
        pass

    @abstractmethod
    def validate_credentials(self) -> tuple[bool, str | None]:
        """Validate if required API keys and endpoint configs exist in environment.
        Returns: (is_configured: bool, error_reason: str | None)
        """
        pass

    @abstractmethod
    def get_models(self) -> list[ModelSpec]:
        """List models supported by this provider, with is_available reflecting credentials."""
        pass

    async def generate_video(
        self,
        prompt: str,
        duration_seconds: int = 5,
        aspect_ratio: str = "16:9",
        reference_image_path: str | None = None,
        model: str | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> GenerationTaskResponse:
        raise NotImplementedError(f"Video generation is not supported by {self.name}")

    async def get_generation_status(self, task_id: str) -> GenerationStatusResponse:
        raise NotImplementedError(f"Generation status polling is not supported by {self.name}")

    async def retrieve_generated_video(
        self,
        task_id: str,
        output_path: str,
        status_payload: GenerationStatusResponse | None = None,
    ) -> str:
        raise NotImplementedError(f"Video retrieval is not supported by {self.name}")

    async def generate_text(
        self,
        prompt: str,
        system_instruction: str | None = None,
        model: str | None = None,
        temperature: float = 0.7,
        max_tokens: int = 4096,
        tools: list[dict[str, Any]] | None = None,
    ) -> dict[str, Any]:
        raise NotImplementedError(f"Text generation is not supported by {self.name}")

    async def generate_speech(
        self,
        text: str,
        output_path: str,
        model: str | None = None,
        voice: str = "coral",
    ) -> str:
        raise NotImplementedError(f"Speech generation is not supported by {self.name}")

    async def generate_image(
        self,
        prompt: str,
        output_path: str,
        model: str | None = None,
        aspect_ratio: str = "16:9",
    ) -> str:
        raise NotImplementedError(f"Image generation is not supported by {self.name}")
