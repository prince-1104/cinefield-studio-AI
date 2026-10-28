"""API endpoints for interactive timeline editing and custom exports."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas.job import JobResponse
from app.schemas.timeline import (
    TimelineEditCreate,
    TimelineEditResponse,
    TimelineEditSummary,
)
from app.services import project_service, timeline_service

router = APIRouter(prefix="/api/projects/{project_id}/timeline", tags=["timeline"])


class ExportRequest(BaseModel):
    timeline_edit_id: uuid.UUID | None = None


@router.get("", response_model=TimelineEditResponse)
async def get_current_timeline(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> TimelineEditResponse:
    """Retrieve the current editable timeline model, bootstrapping from source assets if needed."""
    project = await project_service.get_project(session, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    edit = await timeline_service.get_or_create_default_timeline(session, project)
    await session.commit()
    return TimelineEditResponse.model_validate(edit)


@router.put("", response_model=TimelineEditResponse)
async def save_timeline(
    project_id: uuid.UUID,
    payload: TimelineEditCreate,
    session: AsyncSession = Depends(get_session),
) -> TimelineEditResponse:
    """Save user edits as a new immutable timeline version."""
    project = await project_service.get_project(session, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    edit = await timeline_service.save_timeline_edit(
        session, project_id, payload.timeline_data
    )
    await session.commit()
    return TimelineEditResponse.model_validate(edit)


@router.get("/history", response_model=list[TimelineEditSummary])
async def get_timeline_history(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> list[TimelineEditSummary]:
    """Retrieve version history summaries for this project."""
    project = await project_service.get_project(session, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    return await timeline_service.get_timeline_history(session, project_id)


@router.post("/export", response_model=JobResponse)
async def export_timeline_video(
    project_id: uuid.UUID,
    body: ExportRequest | None = None,
    session: AsyncSession = Depends(get_session),
) -> JobResponse:
    """Queue an FFmpeg render job for the specified or current timeline version."""
    project = await project_service.get_project(session, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    edit_id = body.timeline_edit_id if body else None
    if not edit_id:
        current_edit = await timeline_service.get_or_create_default_timeline(
            session, project
        )
        edit_id = current_edit.id

    try:
        job = await timeline_service.queue_timeline_export(
            session, project_id, edit_id
        )
        await session.commit()
        return JobResponse.model_validate(job)
    except ValueError as e:
        raise HTTPException(status_code=status.HTTP_400_BAD_REQUEST, detail=str(e))

