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


async def create_project(
    session: AsyncSession,
    data: ProjectCreate,
) -> Project:
    """Create a new project in the initial BRIEF stage."""
    project = Project(
        product_name=data.product_name,
        brief=data.brief,
        audience=data.audience,
        tone=data.tone,
        cta=data.cta,
        stage=ProjectStage.BRIEF,
    )
    session.add(project)
    await session.flush()
    # Refresh with empty relationships loaded
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
    return result.scalar_one_or_none()


async def list_projects(
    session: AsyncSession,
) -> Sequence[Project]:
    """List all projects ordered by newest first."""
    stmt = select(Project).order_by(Project.created_at.desc())
    result = await session.execute(stmt)
    return result.scalars().all()


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
        ext = Path(product_image.filename).suffix or ".png"
        dest = upload_dir / f"product_image{ext}"
        with open(dest, "wb") as buffer:
            shutil.copyfileobj(product_image.file, buffer)
        project.product_image_path = str(dest)

    if logo and logo.filename:
        ext = Path(logo.filename).suffix or ".png"
        dest = upload_dir / f"logo{ext}"
        with open(dest, "wb") as buffer:
            shutil.copyfileobj(logo.file, buffer)
        project.logo_path = str(dest)

    if music and music.filename:
        ext = Path(music.filename).suffix or ".mp3"
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
    """Enqueue a PLAN_SCRIPT job to generate script and storyboard."""
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
            "product_image_path": project.product_image_path,
        },
    )
    return job


async def approve_storyboard(
    session: AsyncSession,
    project_id: uuid.UUID,
) -> list[Job]:
    """Approve the storyboard and trigger generation of all 3 video clips plus narration."""
    project = await get_project(session, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    if len(project.shots) != 3:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot approve storyboard: expected exactly 3 shots, found {len(project.shots)}",
        )

    project.stage = ProjectStage.STORYBOARD_APPROVED

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

    job = await job_service.enqueue_job(
        session=session,
        project_id=project_id,
        job_type=JobType.ASSEMBLE,
        payload={
            "product_name": project.product_name,
            "cta": project.cta,
            "logo_path": project.logo_path,
            "music_path": project.music_path,
            "narration_path": project.narration_path,
        },
    )
    return job
