"""Cancellation router for stopping active or queued AI generations, jobs, and shots."""

import uuid
from typing import Any

from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas.project import ProjectCancellationResponse, ShotCancellationResponse
from app.services.cancellation_service import CancellationService

router = APIRouter(prefix="/api", tags=["cancellation"])


@router.post(
    "/projects/{project_id}/cancel-generation",
    response_model=ProjectCancellationResponse,
    summary="Cancel active or queued generation for a project",
)
async def cancel_project_generation(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> ProjectCancellationResponse:
    """Halt all active or queued jobs (storyboard, videos, TTS, assembly) for a project.

    Completed shots and video clips are safely preserved.
    """
    res = await CancellationService.cancel_project_generation(session, project_id)
    return ProjectCancellationResponse(
        project_id=uuid.UUID(res["project_id"]),
        cancelled_jobs_count=res["cancelled_jobs_count"],
        active_cancel_requested_count=res["active_cancel_requested_count"],
        preserved_shots_count=res["preserved_shots_count"],
        cancelled_shots_count=res["cancelled_shots_count"],
        message=res["message"],
    )


@router.post(
    "/jobs/{job_id}/cancel",
    summary="Cancel an individual background job",
)
async def cancel_job(
    job_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> dict[str, Any]:
    """Cancel an individual queued or running job."""
    return await CancellationService.cancel_job(session, job_id)


@router.post(
    "/shots/{shot_id}/cancel-generation",
    response_model=ShotCancellationResponse,
    summary="Cancel video generation for a specific shot",
)
async def cancel_shot_generation(
    shot_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> ShotCancellationResponse:
    """Halt synthesis for an individual shot while preserving all other shots."""
    res = await CancellationService.cancel_shot_generation(session, shot_id)
    return ShotCancellationResponse(
        shot_id=uuid.UUID(res["shot_id"]),
        project_id=uuid.UUID(res["project_id"]),
        status=res["status"],
        message=res["message"],
        provider_task_id=res["provider_task_id"],
        provider_cancellation_supported=res["provider_cancellation_supported"],
    )


@router.post(
    "/projects/{project_id}/shots/{shot_id}/cancel-generation",
    response_model=ShotCancellationResponse,
    summary="Cancel video generation for a specific shot (project-scoped alias)",
)
async def cancel_project_shot_generation(
    project_id: uuid.UUID,
    shot_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> ShotCancellationResponse:
    """Project-scoped alias for cancelling an individual shot."""
    res = await CancellationService.cancel_shot_generation(session, shot_id)
    return ShotCancellationResponse(
        shot_id=uuid.UUID(res["shot_id"]),
        project_id=uuid.UUID(res["project_id"]),
        status=res["status"],
        message=res["message"],
        provider_task_id=res["provider_task_id"],
        provider_cancellation_supported=res["provider_cancellation_supported"],
    )
