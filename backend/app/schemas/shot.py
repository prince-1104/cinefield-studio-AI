"""Pydantic schemas for Shot responses."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class ShotResponse(BaseModel):
    """Read-only representation of a storyboard shot."""

    id: uuid.UUID
    project_id: uuid.UUID
    shot_number: int
    start_time: float = 0.0
    end_time: float = 0.0
    target_duration: float = 5.0
    actual_duration: float | None = None
    description: str
    visual_prompt: str
    camera_motion: str | None = None
    transition: str | None = None
    narration_text: str | None = None
    image_url: str | None = None
    video_path: str | None = None
    provider_job_id: str | None = None
    provider_status: str | None = None
    status: str
    error_message: str | None = None
    retry_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
