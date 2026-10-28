"""Project service orchestrating project lifecycle, file uploads, and job dispatches."""

import os
import shutil
import uuid
from pathlib import Path
from typing import Sequence

from fastapi import HTTPException, UploadFile, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.config import settings
from app.models.job import Job, JobType
from app.models.project import Project, ProjectStage
from app.models.shot import Shot, ShotStatus
from app.schemas.project import ProjectCreate
from app.services import job_service


def update_project_progress(project: Project) -> None:
    """Calculate and set honest, real pipeline progress percentage and stage label."""
    if project.stage == ProjectStage.BRIEF:
        project.progress_percent = 5.0
        project.current_stage_label = "Campaign Brief Defined"
    elif project.stage == ProjectStage.SCRIPT:
        project.progress_percent = 15.0
        project.current_stage_label = "Storyboard Arc Planned (Awaiting Approval)"
    elif project.stage == ProjectStage.STORYBOARD_APPROVED:
        project.progress_percent = 20.0
        project.current_stage_label = "Storyboard Approved · Queuing Production"
    elif project.stage in (ProjectStage.VIDEOS, ProjectStage.NARRATION):
        total_shots = len(project.shots) if project.shots else project.shot_count
        if total_shots <= 0:
            total_shots = 1

        done_shots = len([s for s in project.shots if s.status == ShotStatus.DONE])
        active_shots = len(
            [
                s
                for s in project.shots
                if s.status in (ShotStatus.SUBMITTED, ShotStatus.GENERATING, ShotStatus.DOWNLOADING, ShotStatus.VALIDATING)
            ]
        )

        shots_weight = 55.0  # Shot generation accounts for up to 55% of the pipeline
        shots_progress = ((done_shots + (active_shots * 0.4)) / total_shots) * shots_weight

        narration_weight = 10.0
        narration_progress = narration_weight if project.narration_path else 0.0

        calculated = 20.0 + shots_progress + narration_progress
        project.progress_percent = round(min(calculated, 85.0), 1)
        project.current_stage_label = f"Synthesizing Media ({done_shots}/{total_shots} Clips Ready)"
    elif project.stage == ProjectStage.RENDERING:
        project.progress_percent = 90.0
        project.current_stage_label = "Rendering 1080p Cinema Master in FFmpeg"
    elif project.stage == ProjectStage.ASSEMBLED:
        project.progress_percent = 100.0
        project.current_stage_label = "Cinema Master Delivered & Verified"
    elif project.stage == ProjectStage.FAILED:
        project.current_stage_label = "Production Interrupted"


async def create_project(
    session: AsyncSession,
    data: ProjectCreate,
) -> Project:
    """Create a new project in the initial BRIEF stage with target duration and shot count."""
    project = Project(
        product_name=data.product_name,
        brief=data.brief,
        audience=data.audience,
        tone=data.tone,
        cta=data.cta,
        target_duration=data.target_duration,
        shot_count=data.shot_count,
        aspect_ratio=data.aspect_ratio,
        stage=ProjectStage.BRIEF,
        progress_percent=5.0,
        current_stage_label="Campaign Brief Defined",
    )
    session.add(project)
    await session.flush()
    return await get_project(session, project.id)  # type: ignore


async def get_project(
    session: AsyncSession,
    project_id: uuid.UUID,
) -> Project | None:
    """Get project by ID with shots and jobs eagerly loaded."""
    stmt = (
        select(Project)
        .where(Project.id == project_id)
        .options(
            selectinload(Project.shots),
            selectinload(Project.jobs),
        )
    )
    result = await session.execute(stmt)
    project = result.scalar_one_or_none()
    if project:
        update_project_progress(project)
    return project


async def list_projects(
    session: AsyncSession,
) -> Sequence[Project]:
    """List all projects ordered by newest first."""
    stmt = (
        select(Project)
        .options(selectinload(Project.shots))
        .order_by(Project.created_at.desc())
    )
    result = await session.execute(stmt)
    projects = result.scalars().all()
    for p in projects:
        update_project_progress(p)
    return projects


def _safe_ext(filename: str | None, default: str) -> str:
    """Sanitize file extension to prevent path traversal and arbitrary file types."""
    if not filename:
        return default
    ext = Path(filename).suffix.lower()
    if ext in (".png", ".jpg", ".jpeg", ".webp", ".mp3", ".wav", ".aac", ".m4a"):
        return ext
    return default


async def save_uploaded_assets(
    session: AsyncSession,
    project_id: uuid.UUID,
    product_image: UploadFile | None = None,
    logo: UploadFile | None = None,
    music: UploadFile | None = None,
) -> Project:
    """Save uploaded asset files to the artifact directory and update the project."""
    project = await get_project(session, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    upload_dir = Path(settings.ARTIFACT_DIR) / "projects" / str(project_id) / "uploads"
    upload_dir.mkdir(parents=True, exist_ok=True)

    if product_image and product_image.filename:
        ext = _safe_ext(product_image.filename, ".png")
        dest = upload_dir / f"product_image{ext}"
        with open(dest, "wb") as buffer:
            shutil.copyfileobj(product_image.file, buffer)
        project.product_image_path = str(dest)

    if logo and logo.filename:
        ext = _safe_ext(logo.filename, ".png")
        dest = upload_dir / f"logo{ext}"
        with open(dest, "wb") as buffer:
            shutil.copyfileobj(logo.file, buffer)
        project.logo_path = str(dest)

    if music and music.filename:
        ext = _safe_ext(music.filename, ".mp3")
        dest = upload_dir / f"music{ext}"
        with open(dest, "wb") as buffer:
            shutil.copyfileobj(music.file, buffer)
        project.music_path = str(dest)

    await session.flush()
    refreshed = await get_project(session, project_id)
    return refreshed  # type: ignore


async def request_script_generation(
    session: AsyncSession,
    project_id: uuid.UUID,
) -> Job:
    """Enqueue a PLAN_SCRIPT job with target duration and shot count."""
    project = await get_project(session, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    job = await job_service.enqueue_job(
        session=session,
        project_id=project_id,
        job_type=JobType.PLAN_SCRIPT,
        payload={
            "product_name": project.product_name,
            "brief": project.brief,
            "audience": project.audience,
            "tone": project.tone,
            "cta": project.cta,
            "target_duration": project.target_duration,
            "shot_count": project.shot_count,
            "aspect_ratio": project.aspect_ratio,
            "product_image_path": project.product_image_path,
        },
    )
    return job


async def approve_storyboard(
    session: AsyncSession,
    project_id: uuid.UUID,
) -> list[Job]:
    """Approve the storyboard and trigger generation of all sequential video clips plus narration."""
    project = await get_project(session, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    if not project.shots or len(project.shots) == 0:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cannot approve storyboard: no shots found in project.",
        )

    project.stage = ProjectStage.STORYBOARD_APPROVED
    update_project_progress(project)

    jobs: list[Job] = []

    # Enqueue parallel video generation jobs for each shot
    for shot in project.shots:
        shot.status = ShotStatus.PENDING
        shot.error_message = None
        job = await job_service.enqueue_job(
            session=session,
            project_id=project_id,
            job_type=JobType.GENERATE_VIDEO,
            payload={
                "shot_id": str(shot.id),
                "shot_number": shot.shot_number,
                "visual_prompt": shot.visual_prompt,
                "description": shot.description,
                "camera_motion": shot.camera_motion,
                "transition": shot.transition,
                "target_duration": shot.target_duration,
                "aspect_ratio": project.aspect_ratio,
                "product_image_path": project.product_image_path,
            },
        )
        jobs.append(job)

    # Enqueue TTS narration job
    full_narration = " ".join(
        [s.narration_text for s in project.shots if s.narration_text]
    )
    if not full_narration and project.script:
        full_narration = project.script

    tts_job = await job_service.enqueue_job(
        session=session,
        project_id=project_id,
        job_type=JobType.GENERATE_TTS,
        payload={
            "text": full_narration,
            "cta": project.cta,
            "target_duration": project.target_duration,
        },
    )
    jobs.append(tts_job)

    await session.flush()
    return jobs


async def retry_shot(
    session: AsyncSession,
    project_id: uuid.UUID,
    shot_id: uuid.UUID,
) -> Job:
    """Retry generation for a specific shot without re-generating successful ones."""
    project = await get_project(session, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    shot = next((s for s in project.shots if s.id == shot_id), None)
    if not shot:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Shot {shot_id} not found in project {project_id}",
        )

    shot.status = ShotStatus.PENDING
    shot.error_message = None
    shot.retry_count += 1

    job = await job_service.enqueue_job(
        session=session,
        project_id=project_id,
        job_type=JobType.GENERATE_VIDEO,
        payload={
            "shot_id": str(shot.id),
            "shot_number": shot.shot_number,
            "visual_prompt": shot.visual_prompt,
            "description": shot.description,
            "camera_motion": shot.camera_motion,
            "transition": shot.transition,
            "target_duration": shot.target_duration,
            "aspect_ratio": project.aspect_ratio,
            "product_image_path": project.product_image_path,
        },
    )
    await session.flush()
    return job


async def request_tts(
    session: AsyncSession,
    project_id: uuid.UUID,
) -> Job:
    """Trigger or re-trigger TTS narration generation."""
    project = await get_project(session, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    full_narration = " ".join(
        [s.narration_text for s in project.shots if s.narration_text]
    )
    if not full_narration and project.script:
        full_narration = project.script

    job = await job_service.enqueue_job(
        session=session,
        project_id=project_id,
        job_type=JobType.GENERATE_TTS,
        payload={
            "text": full_narration,
            "cta": project.cta,
            "target_duration": project.target_duration,
        },
    )
    return job


async def request_assembly(
    session: AsyncSession,
    project_id: uuid.UUID,
) -> Job:
    """Enqueue the final ASSEMBLE job to render MP4 video with clips, audio, captions, and CTA."""
    project = await get_project(session, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    project.stage = ProjectStage.RENDERING
    update_project_progress(project)
    await session.flush()

    job = await job_service.enqueue_job(
        session=session,
        project_id=project_id,
        job_type=JobType.ASSEMBLE,
        payload={
            "product_name": project.product_name,
            "cta": project.cta,
            "target_duration": project.target_duration,
            "aspect_ratio": project.aspect_ratio,
            "logo_path": project.logo_path,
            "music_path": project.music_path,
            "narration_path": project.narration_path,
        },
    )
    return job
