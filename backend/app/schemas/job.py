"""Pydantic schemas for Job responses."""

import uuid
from datetime import datetime
from typing import Any

from pydantic import BaseModel


class JobResponse(BaseModel):
    """Read-only representation of a background job."""

    id: uuid.UUID
    project_id: uuid.UUID
    job_type: str
    status: str
    payload: dict[str, Any] | None = None
    result: dict[str, Any] | None = None
    error_message: str | None = None
    attempt: int
    started_at: datetime | None = None
    completed_at: datetime | None = None
    created_at: datetime
    updated_at: datetime

    model_config = {"from_attributes": True}
