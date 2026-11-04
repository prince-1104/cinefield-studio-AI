"""Project API endpoints for creation, asset uploads, pipeline triggers, and downloads."""

import os
import uuid
from pathlib import Path
from typing import Sequence

from fastapi import (
    APIRouter,
    Depends,
    File,
    HTTPException,
    Query,
    UploadFile,
    status,
)
from fastapi.responses import FileResponse
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import get_session
from app.schemas.job import JobResponse
from app.schemas.project import (
    ModelSelectionPayload,
    ProjectCreate,
    ProjectDetail,
    ProjectSummary,
    ShotGenerationPayload,
)
from app.schemas.shot import ShotPromptUpdate, ShotResponse
from app.services import project_service
from app.services.video_providers import VideoModelInfo, provider_registry

router = APIRouter(prefix="/api/projects", tags=["projects"])


@router.get("/video-models", response_model=list[VideoModelInfo])
async def list_video_models() -> list[VideoModelInfo]:
    """List all available video generation models across providers (Seedance, Gemini)."""
    return provider_registry.list_available_models()


@router.post("", response_model=ProjectDetail, status_code=status.HTTP_201_CREATED)
async def create_project(
    data: ProjectCreate,
    session: AsyncSession = Depends(get_session),
) -> ProjectDetail:
    """Create a new ad project in the initial BRIEF stage."""
    project = await project_service.create_project(session, data)
    return ProjectDetail.model_validate(project)


@router.get("", response_model=list[ProjectSummary])
async def list_projects(
    session: AsyncSession = Depends(get_session),
) -> Sequence[ProjectSummary]:
    """List all projects ordered by newest first."""
    projects = await project_service.list_projects(session)
    return [ProjectSummary.model_validate(p) for p in projects]


@router.get("/{project_id}", response_model=ProjectDetail)
async def get_project(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> ProjectDetail:
    """Get project details including all 3 shots and jobs."""
    project = await project_service.get_project(session, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )
    return ProjectDetail.model_validate(project)


@router.post("/{project_id}/uploads", response_model=ProjectDetail)
async def upload_assets(
    project_id: uuid.UUID,
    product_image: UploadFile | None = File(None),
    logo: UploadFile | None = File(None),
    music: UploadFile | None = File(None),
    session: AsyncSession = Depends(get_session),
) -> ProjectDetail:
    """Upload product reference image, logo, or background music."""
    project = await project_service.save_uploaded_assets(
        session=session,
        project_id=project_id,
        product_image=product_image,
        logo=logo,
        music=music,
    )
    return ProjectDetail.model_validate(project)


@router.post("/{project_id}/generate-script", response_model=JobResponse)
async def generate_script(
    project_id: uuid.UUID,
    force_template: bool = Query(default=False),
    session: AsyncSession = Depends(get_session),
) -> JobResponse:
    """Trigger AI generation of the script and 3-shot storyboard."""
    job = await project_service.request_script_generation(session, project_id, force_template=force_template)
    return JobResponse.model_validate(job)


@router.put("/{project_id}/model", response_model=ProjectDetail)
async def select_project_model(
    project_id: uuid.UUID,
    payload: ModelSelectionPayload,
    session: AsyncSession = Depends(get_session),
) -> ProjectDetail:
    """Select the active video generation model and provider for a project."""
    project = await project_service.update_project_model(
        session=session,
        project_id=project_id,
        model=payload.model,
        provider=payload.provider,
    )
    return ProjectDetail.model_validate(project)


@router.put("/{project_id}/shots/{shot_id}/prompt", response_model=ShotResponse)
async def update_shot_prompt(
    project_id: uuid.UUID,
    shot_id: uuid.UUID,
    payload: ShotPromptUpdate,
    session: AsyncSession = Depends(get_session),
) -> ShotResponse:
    """Edit the visual generation prompt for a specific shot."""
    shot = await project_service.update_shot_prompt(
        session=session,
        project_id=project_id,
        shot_id=shot_id,
        visual_prompt=payload.visual_prompt,
    )
    return ShotResponse.model_validate(shot)


@router.post("/{project_id}/shots/{shot_id}/generate", response_model=JobResponse)
async def generate_shot(
    project_id: uuid.UUID,
    shot_id: uuid.UUID,
    payload: ShotGenerationPayload | None = None,
    session: AsyncSession = Depends(get_session),
) -> JobResponse:
    """Trigger generation of a single shot with optional prompt or model override."""
    prompt = payload.prompt if payload else None
    model = payload.model if payload else None
    provider = payload.provider if payload else None
    job = await project_service.generate_shot_video(
        session=session,
        project_id=project_id,
        shot_id=shot_id,
        prompt=prompt,
        model=model,
        provider=provider,
    )
    return JobResponse.model_validate(job)


@router.post("/{project_id}/approve", response_model=list[JobResponse])
async def approve_storyboard(
    project_id: uuid.UUID,
    payload: ModelSelectionPayload | None = None,
    session: AsyncSession = Depends(get_session),
) -> list[JobResponse]:
    """Approve storyboard and enqueue parallel video clips and narration generation."""
    model = payload.model if payload else None
    provider = payload.provider if payload else None
    jobs = await project_service.approve_storyboard(
        session=session,
        project_id=project_id,
        model=model,
        provider=provider,
    )
    return [JobResponse.model_validate(j) for j in jobs]


@router.post("/{project_id}/shots/{shot_id}/retry", response_model=JobResponse)
async def retry_shot(
    project_id: uuid.UUID,
    shot_id: uuid.UUID,
    payload: ShotGenerationPayload | None = None,
    session: AsyncSession = Depends(get_session),
) -> JobResponse:
    """Retry generation of a specific failed shot."""
    model = payload.model if payload else None
    provider = payload.provider if payload else None
    job = await project_service.retry_shot(
        session=session,
        project_id=project_id,
        shot_id=shot_id,
        model=model,
        provider=provider,
    )
    return JobResponse.model_validate(job)


@router.post("/{project_id}/generate-tts", response_model=JobResponse)
async def generate_tts(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> JobResponse:
    """Trigger or retry text-to-speech narration generation."""
    job = await project_service.request_tts(session, project_id)
    return JobResponse.model_validate(job)


@router.post("/{project_id}/assemble", response_model=JobResponse)
async def assemble_video(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> JobResponse:
    """Trigger the FFmpeg assembly job."""
    job = await project_service.request_assembly(session, project_id)
    return JobResponse.model_validate(job)


@router.get("/{project_id}/download")
async def download_ad(
    project_id: uuid.UUID,
    session: AsyncSession = Depends(get_session),
) -> FileResponse:
    """Download the final produced advertisement MP4 file."""
    project = await project_service.get_project(session, project_id)
    if not project:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Project {project_id} not found",
        )

    if not project.final_video_path or not os.path.exists(project.final_video_path):
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Final video has not been rendered yet.",
        )

    sanitized_name = "".join(
        c for c in project.product_name if c.isalnum() or c in (" ", "-", "_")
    ).rstrip()
    download_filename = f"{sanitized_name}_ad.mp4"

    return FileResponse(
        path=project.final_video_path,
        media_type="video/mp4",
        filename=download_filename,
    )

