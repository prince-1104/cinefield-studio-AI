"""Pydantic schemas for Project CRUD and responses."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel, Field

from app.schemas.job import JobResponse
from app.schemas.shot import ShotResponse


# ── Request schemas ──────────────────────────────────────────────

class ProjectCreate(BaseModel):
    """Payload for creating a new project."""

    product_name: str = Field(..., min_length=1, max_length=255)
    brief: str = Field(..., min_length=1)
    audience: str = Field(..., min_length=1, max_length=500)
    tone: str = Field(..., min_length=1, max_length=255)
    cta: str = Field(..., min_length=1)

    # Production specifications
    target_duration: int = Field(default=15, ge=10, le=120, description="Target total video duration in seconds")
    shot_count: int = Field(default=3, ge=1, le=16, description="Planned number of sequential storyboard shots")
    aspect_ratio: str = Field(default="16:9", description="Aspect ratio: '16:9' or '9:16'")
    selected_video_model: str | None = Field(default="seedance-1-0-pro-250528", description="Selected video generation model")
    selected_video_provider: str | None = Field(default="seedance", description="Selected video generation provider")


class ModelSelectionPayload(BaseModel):
    """Payload for updating project model selection."""

    model: str = Field(..., description="Selected model identifier (e.g. 'seedance-1-0-pro-250528')")
    provider: str | None = Field(default=None, description="Optional provider identifier (e.g. 'seedance')")


class ShotGenerationPayload(BaseModel):
    """Payload for triggering generation of a single shot."""

    prompt: str | None = None
    model: str | None = None
    provider: str | None = None


class ProjectCancellationResponse(BaseModel):
    """Structured response after requesting project-level generation cancellation."""

    project_id: uuid.UUID
    cancelled_jobs_count: int
    active_cancel_requested_count: int
    preserved_shots_count: int
    cancelled_shots_count: int
    message: str


class ShotCancellationResponse(BaseModel):
    """Structured response after requesting individual shot generation cancellation."""

    shot_id: uuid.UUID
    project_id: uuid.UUID
    status: str
    message: str
    provider_task_id: str | None = None
    provider_cancellation_supported: bool = False


# ── Response schemas ─────────────────────────────────────────────

class ProjectSummary(BaseModel):
    """Lightweight project representation for list views."""

    id: uuid.UUID
    product_name: str
    stage: str
    target_duration: int = 15
    shot_count: int = 3
    progress_percent: float = 0.0
    selected_video_model: str | None = "seedance-1-0-pro-250528"
    selected_video_provider: str | None = "seedance"
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectDetail(BaseModel):
    """Full project representation with nested shots, jobs, and production metrics."""

    id: uuid.UUID
    product_name: str
    brief: str
    audience: str
    tone: str
    cta: str

    target_duration: int = 15
    shot_count: int = 3
    aspect_ratio: str = "16:9"
    selected_video_model: str | None = "seedance-1-0-pro-250528"
    selected_video_provider: str | None = "seedance"
    progress_percent: float = 0.0
    current_stage_label: str | None = None

    script: str | None = None
    stage: str
    product_image_path: str | None = None
    logo_path: str | None = None
    music_path: str | None = None
    narration_path: str | None = None
    final_video_path: str | None = None
    video_metadata: dict[str, Any] | None = None

    created_at: datetime
    updated_at: datetime
    shots: list[ShotResponse] = []
    jobs: list[JobResponse] = []

    model_config = {"from_attributes": True}
