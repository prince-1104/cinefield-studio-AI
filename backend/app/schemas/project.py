"""Pydantic schemas for Project CRUD and responses."""

import uuid
from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.shot import ShotResponse
from app.schemas.job import JobResponse


# ── Request schemas ──────────────────────────────────────────────

class ProjectCreate(BaseModel):
    """Payload for creating a new project."""

    product_name: str = Field(..., min_length=1, max_length=255)
    brief: str = Field(..., min_length=1)
    audience: str = Field(..., min_length=1, max_length=500)
    tone: str = Field(..., min_length=1, max_length=255)
    cta: str = Field(..., min_length=1)


# ── Response schemas ─────────────────────────────────────────────

class ProjectSummary(BaseModel):
    """Lightweight project representation for list views."""

    id: uuid.UUID
    product_name: str
    stage: str
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}


class ProjectDetail(BaseModel):
    """Full project representation with nested shots and jobs."""

    id: uuid.UUID
    product_name: str
    brief: str
    audience: str
    tone: str
    cta: str
    script: str | None = None
    stage: str
    product_image_path: str | None = None
    logo_path: str | None = None
    music_path: str | None = None
    narration_path: str | None = None
    final_video_path: str | None = None
    created_at: datetime
    updated_at: datetime
    shots: list[ShotResponse] = []
    jobs: list[JobResponse] = []

    model_config = {"from_attributes": True}
