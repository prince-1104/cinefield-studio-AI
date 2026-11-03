"""Base interfaces and data models for video generation providers."""

from abc import ABC, abstractmethod
from typing import Any
from pydantic import BaseModel, Field


class VideoModelInfo(BaseModel):
    """Metadata describing a video generation model."""

    id: str = Field(..., description="Unique model identifier used in API calls")
    name: str = Field(..., description="Human-readable model name")
    provider: str = Field(..., description="Provider identifier (e.g. 'seedance', 'gemini')")
    provider_name: str = Field(..., description="Display name of the provider")
    description: str = Field(..., description="Short summary of model capabilities and characteristics")
    supported_aspect_ratios: list[str] = Field(default_factory=lambda: ["16:9", "9:16"])
    supported_durations: list[int] = Field(default_factory=lambda: [5])
    default_duration: int = 5
    is_default: bool = False
    requires_resource_id: bool = False
    capabilities: list[str] = Field(default_factory=list)


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


class BaseVideoProvider(ABC):
    """Abstract base class for all AI video generation providers."""

    @property
    @abstractmethod
    def provider_id(self) -> str:
        """Machine identifier (e.g. 'seedance', 'gemini')."""
        pass

    @property
    @abstractmethod
    def name(self) -> str:
        """Display name (e.g. 'ByteDance Seedance')."""
        pass

    @abstractmethod
    def get_models(self) -> list[VideoModelInfo]:
        """List models supported by this provider."""
        pass

    @abstractmethod
    async def generate_video(
        self,
        prompt: str,
        duration_seconds: int = 5,
        aspect_ratio: str = "16:9",
        reference_image_path: str | None = None,
        model: str | None = None,
        parameters: dict[str, Any] | None = None,
    ) -> GenerationTaskResponse:
        """Submit a video generation task to the provider API."""
        pass

    @abstractmethod
    async def get_generation_status(
        self,
        task_id: str,
    ) -> GenerationStatusResponse:
        """Poll the provider API for the status of an ongoing task."""
        pass

    @abstractmethod
    async def retrieve_generated_video(
        self,
        task_id: str,
        output_path: str,
        status_payload: GenerationStatusResponse | None = None,
    ) -> str:
        """Download or fetch the generated video stream and save it to output_path."""
        pass

