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


# ── Response schemas ─────────────────────────────────────────────

class ProjectSummary(BaseModel):
    """Lightweight project representation for list views."""

    id: uuid.UUID
    product_name: str
    stage: str
    target_duration: int = 15
    shot_count: int = 3
    progress_percent: float = 0.0
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
