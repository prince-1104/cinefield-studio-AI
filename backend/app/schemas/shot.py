"""Pydantic schemas for Shot responses."""

import uuid
from datetime import datetime

from pydantic import BaseModel


class ShotResponse(BaseModel):
    """Read-only representation of a storyboard shot."""

    id: uuid.UUID
    project_id: uuid.UUID
    shot_number: int
    description: str
    visual_prompt: str
    narration_text: str | None = None
    image_url: str | None = None
    video_path: str | None = None
    status: str
    error_message: str | None = None
    retry_count: int
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
