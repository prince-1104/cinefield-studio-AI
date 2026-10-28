"""Job queue service for managing asynchronous background tasks."""

import uuid
from typing import Any

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job, JobStatus, JobType


async def enqueue_job(
    session: AsyncSession,
    project_id: uuid.UUID,
    job_type: JobType,
    payload: dict[str, Any] | None = None,
) -> Job:
    """Create and enqueue a new background job."""
    job = Job(
        project_id=project_id,
        job_type=job_type,
        status=JobStatus.QUEUED,
        payload=payload or {},
        attempt=1,
    )
    session.add(job)
    await session.flush()
    return job


async def get_jobs_for_project(
    session: AsyncSession,
    project_id: uuid.UUID,
) -> list[Job]:
    """Retrieve all jobs associated with a project, ordered by creation time."""
    stmt = (
        select(Job)
        .where(Job.project_id == project_id)
        .order_by(Job.created_at.asc())
    )
    result = await session.execute(stmt)
    return list(result.scalars().all())


async def get_job_by_id(
    session: AsyncSession,
    job_id: uuid.UUID,
) -> Job | None:
    """Retrieve a single job by UUID."""
    stmt = select(Job).where(Job.id == job_id)
    result = await session.execute(stmt)
    return result.scalar_one_or_none()


async def get_next_queued_job(
    session: AsyncSession,
) -> Job | None:
    """Retrieve the oldest QUEUED job (used by the worker in P4)."""
    stmt = (
        select(Job)
        .where(Job.status == JobStatus.QUEUED)
        .order_by(Job.created_at.asc())
        .limit(1)
        .with_for_update(skip_locked=True)
    )
    result = await session.execute(stmt)
    return result.scalar_one_or_none()
