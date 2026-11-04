"""Centralized cancellation service for AI generation, jobs, shots, and pipelines."""

import logging
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import HTTPException, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.models.job import Job, JobStatus, JobType
from app.models.project import Project, ProjectStage
from app.models.shot import Shot, ShotStatus
from app.services.project_service import get_project, update_project_progress
from app.services.video_providers import provider_registry

logger = logging.getLogger(__name__)


class CancellationService:
    """Manages coordinated, cooperative cancellation across project, job, and shot scopes."""

    @classmethod
    async def cancel_project_generation(
        cls,
        session: AsyncSession,
        project_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Cancel all queued and active generation operations for a project.

        Preserves all completed shots and generated video clips.
        Cancels queued jobs immediately and requests cancellation for running worker jobs.
        """
        project = await session.execute(
            select(Project)
            .where(Project.id == project_id)
            .options(selectinload(Project.shots), selectinload(Project.jobs))
        )
        proj = project.scalar_one_or_none()
        if not proj:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project {project_id} not found",
            )

        now = datetime.now(timezone.utc)
        cancelled_jobs_count = 0
        active_cancel_requested_count = 0
        preserved_shots_count = 0
        cancelled_shots_count = 0
        provider_cancellation_notes: list[str] = []

        # 1. Process active and queued background jobs
        for job in proj.jobs:
            if job.status == JobStatus.QUEUED:
                job.status = JobStatus.CANCELLED
                job.completed_at = now
                job.error_message = "Generation cancelled by user before execution."
                cancelled_jobs_count += 1
                logger.info(f"Cancelled queued job {job.id} (type={job.job_type.value}) for project {proj.id}")
            elif job.status in (JobStatus.RUNNING, JobStatus.CLAIMED):
                job.status = JobStatus.CANCEL_REQUESTED
                job.error_message = "Cancellation requested by user during active execution."
                active_cancel_requested_count += 1
                logger.info(f"Requested cancellation for active running job {job.id} (type={job.job_type.value})")

        # 2. Process shots
        for shot in proj.shots:
            if shot.status in (ShotStatus.DONE, ShotStatus.COMPLETED):
                preserved_shots_count += 1
                continue

            if shot.status in (ShotStatus.PENDING, ShotStatus.QUEUED):
                shot.status = ShotStatus.CANCELLED
                shot.completed_at = now
                shot.error_message = "Shot generation cancelled before synthesis started."
                cancelled_shots_count += 1
            elif shot.status in (
                ShotStatus.CLAIMED,
                ShotStatus.SUBMITTED,
                ShotStatus.GENERATING,
                ShotStatus.DOWNLOADING,
                ShotStatus.VALIDATING,
                ShotStatus.RETRYING,
            ):
                shot.status = ShotStatus.CANCEL_REQUESTED
                shot.error_message = "Cancellation requested by user during active synthesis."
                cancelled_shots_count += 1

                # If a remote provider task exists, invoke provider cancellation
                if shot.provider_job_id:
                    try:
                        provider, _ = provider_registry.get_provider_for_model(
                            shot.model or proj.selected_video_model or "seedance-1-0-pro-250528"
                        )
                        cancel_resp = await provider.cancel_generation(shot.provider_job_id)
                        if not cancel_resp.supported:
                            provider_cancellation_notes.append(
                                f"Shot {shot.shot_number}: {cancel_resp.message}"
                            )
                    except Exception as err:
                        logger.warning(f"Could not call provider cancel for shot {shot.id}: {err}")

        # 3. Update Project Stage appropriately
        if proj.stage in (ProjectStage.ASSEMBLY_QUEUED, ProjectStage.ASSEMBLING, ProjectStage.RENDERING):
            proj.stage = ProjectStage.STORYBOARD_APPROVED
            proj.current_stage_label = "Final video assembly was cancelled. Clips and timeline are preserved."
        elif proj.stage == ProjectStage.BRIEF:
            proj.current_stage_label = "Brief & storyboard generation cancelled by user."
        elif proj.stage == ProjectStage.SCRIPT:
            # If storyboard generation was in progress and cancelled
            if not proj.shots or len(proj.shots) == 0:
                proj.stage = ProjectStage.BRIEF
                proj.current_stage_label = "Storyboard generation cancelled by user. Parameters preserved."
            else:
                proj.stage = ProjectStage.SCRIPT
                proj.current_stage_label = "Storyboard generation stopped."
        elif proj.stage in (ProjectStage.STORYBOARD_APPROVED, ProjectStage.VIDEOS, ProjectStage.NARRATION):
            if preserved_shots_count > 0:
                proj.current_stage_label = (
                    f"Video generation stopped. {preserved_shots_count} clip(s) preserved, "
                    f"{cancelled_shots_count} shot(s) cancelled."
                )
            else:
                proj.current_stage_label = "Video generation stopped. You can modify prompts, switch models, or restart."

        update_project_progress(proj)
        await session.commit()

        message = (
            f"Generation cancelled for project '{proj.product_name}'. "
            f"{cancelled_jobs_count} queued jobs cancelled, {active_cancel_requested_count} active jobs flagged to stop. "
            f"{preserved_shots_count} completed clips safely preserved."
        )

        return {
            "project_id": str(proj.id),
            "cancelled_jobs_count": cancelled_jobs_count,
            "active_cancel_requested_count": active_cancel_requested_count,
            "preserved_shots_count": preserved_shots_count,
            "cancelled_shots_count": cancelled_shots_count,
            "provider_notes": provider_cancellation_notes,
            "message": message,
        }

    @classmethod
    async def cancel_job(
        cls,
        session: AsyncSession,
        job_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Cancel a single background job by ID."""
        job = await session.get(Job, job_id)
        if not job:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Job {job_id} not found",
            )

        now = datetime.now(timezone.utc)
        prev_status = job.status.value

        if job.status == JobStatus.QUEUED:
            job.status = JobStatus.CANCELLED
            job.completed_at = now
            job.error_message = "Cancelled by user before execution."
        elif job.status in (JobStatus.RUNNING, JobStatus.CLAIMED):
            job.status = JobStatus.CANCEL_REQUESTED
            job.error_message = "Cancellation requested by user during execution."
        elif job.status in (JobStatus.DONE, JobStatus.CANCELLED, JobStatus.FAILED):
            return {
                "job_id": str(job.id),
                "status": job.status.value,
                "previous_status": prev_status,
                "message": f"Job {job.id} is already in terminal state '{job.status.value}'.",
            }

        # If job is associated with a shot, coordinate shot status
        if job.job_type == JobType.GENERATE_VIDEO and job.payload and "shot_id" in job.payload:
            try:
                shot_id = uuid.UUID(job.payload["shot_id"])
                shot = await session.get(Shot, shot_id)
                if shot and shot.status not in (ShotStatus.DONE, ShotStatus.COMPLETED):
                    if job.status == JobStatus.CANCELLED:
                        shot.status = ShotStatus.CANCELLED
                        shot.completed_at = now
                    else:
                        shot.status = ShotStatus.CANCEL_REQUESTED
            except Exception as err:
                logger.warning(f"Could not update shot status for job {job.id}: {err}")

        # Update parent project progress
        project = await session.get(Project, job.project_id)
        if project:
            update_project_progress(project)

        await session.commit()
        return {
            "job_id": str(job.id),
            "status": job.status.value,
            "previous_status": prev_status,
            "message": f"Job {job.id} transitioned to '{job.status.value}'.",
        }

    @classmethod
    async def cancel_shot_generation(
        cls,
        session: AsyncSession,
        shot_id: uuid.UUID,
    ) -> dict[str, Any]:
        """Cancel generation for an individual shot while preserving all other shots."""
        shot = await session.get(Shot, shot_id)
        if not shot:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Shot {shot_id} not found",
            )

        if shot.status in (ShotStatus.DONE, ShotStatus.COMPLETED):
            raise HTTPException(
                status_code=status.HTTP_400_BAD_REQUEST,
                detail=f"Shot {shot.shot_number} is already completed. Completed clips are preserved and cannot be cancelled.",
            )

        now = datetime.now(timezone.utc)
        prev_status = shot.status.value
        provider_supported = False
        provider_message = ""

        # Find any active job associated with this shot
        from app.services.job_service import find_active_job_for_shot
        active_job = await find_active_job_for_shot(session, shot.project_id, shot.id)

        if shot.status in (ShotStatus.PENDING, ShotStatus.QUEUED):
            shot.status = ShotStatus.CANCELLED
            shot.completed_at = now
            shot.error_message = "Cancelled by user before synthesis started."
            if active_job:
                active_job.status = JobStatus.CANCELLED
                active_job.completed_at = now
                active_job.error_message = "Shot cancelled by user."
        else:
            shot.status = ShotStatus.CANCEL_REQUESTED
            shot.error_message = "Cancellation requested by user."
            if active_job:
                active_job.status = JobStatus.CANCEL_REQUESTED
                active_job.error_message = "Cancellation requested by user."

            # Check provider cancellation
            if shot.provider_job_id:
                try:
                    project = await session.get(Project, shot.project_id)
                    model_to_use = shot.model or (project.selected_video_model if project else None) or "seedance-1-0-pro-250528"
                    provider, _ = provider_registry.get_provider_for_model(model_to_use)
                    cancel_resp = await provider.cancel_generation(shot.provider_job_id)
                    provider_supported = cancel_resp.supported
                    provider_message = cancel_resp.message
                except Exception as err:
                    logger.warning(f"Error querying provider cancellation for shot {shot.id}: {err}")

        project = await session.get(Project, shot.project_id)
        if project:
            update_project_progress(project)

        await session.commit()

        return {
            "shot_id": str(shot.id),
            "project_id": str(shot.project_id),
            "shot_number": shot.shot_number,
            "status": shot.status.value,
            "previous_status": prev_status,
            "provider_task_id": shot.provider_job_id,
            "provider_cancellation_supported": provider_supported,
            "message": (
                provider_message
                if provider_message
                else f"Shot {shot.shot_number} generation cancelled. Status: {shot.status.value}."
            ),
        }

