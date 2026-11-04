"""Server-Sent Events (SSE) router for real-time project progress and shot event streaming."""

import asyncio
import json
import uuid
from datetime import datetime, timezone
from typing import AsyncGenerator

from fastapi import APIRouter, HTTPException, Request, status
from sse_starlette.sse import EventSourceResponse

from app.database import async_session_factory
from app.schemas.project import ProjectDetail
from app.services import project_service

router = APIRouter(prefix="/api/projects", tags=["events"])


@router.get("/{project_id}/events")
async def stream_project_events(
    project_id: uuid.UUID,
    request: Request,
) -> EventSourceResponse:
    """Stream real-time status and live progress updates for a project via SSE."""

    # First verify the project exists
    async with async_session_factory() as session:
        initial = await project_service.get_project(session, project_id)
        if not initial:
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=f"Project {project_id} not found",
            )

    async def event_generator() -> AsyncGenerator[dict[str, str], None]:
        last_signature: str | None = None
        last_shot_states: dict[str, str] = {}
        last_job_states: dict[str, str] = {}
        last_stage: str | None = None

        while True:
            if await request.is_disconnected():
                break

            try:
                async with async_session_factory() as session:
                    project = await project_service.get_project(session, project_id)
                    if not project:
                        break

                    detail = ProjectDetail.model_validate(project)
                    now_iso = datetime.now(timezone.utc).isoformat()

                    # Check for stage change event
                    current_stage_str = str(detail.stage)
                    if last_stage is not None and current_stage_str != last_stage:
                        stage_event = {
                            "event_type": "STAGE_TRANSITION",
                            "project_id": str(project_id),
                            "stage": current_stage_str,
                            "stage_label": detail.current_stage_label or current_stage_str,
                            "progress_percent": detail.progress_percent,
                            "timestamp": now_iso,
                        }
                        yield {
                            "event": "generation_progress",
                            "data": json.dumps(stage_event),
                        }
                    last_stage = current_stage_str

                    # Check for individual shot state transitions
                    for shot in detail.shots:
                        shot_key = str(shot.id)
                        shot_status_str = str(shot.status)
                        prev_status = last_shot_states.get(shot_key)

                        if prev_status is not None and prev_status != shot_status_str:
                            # Match relevant job if exists
                            matched_job = next(
                                (j for j in detail.jobs if j.payload and j.payload.get("shot_id") == shot_key),
                                None,
                            )
                            shot_event = {
                                "event_type": "SHOT_UPDATE",
                                "project_id": str(project_id),
                                "shot_id": shot_key,
                                "shot_number": shot.shot_number,
                                "job_id": str(matched_job.id) if matched_job else None,
                                "provider": shot.provider or detail.selected_video_provider,
                                "model": shot.model or detail.selected_video_model,
                                "status": shot_status_str,
                                "previous_status": prev_status,
                                "error": shot.error_message,
                                "video_path": shot.video_path,
                                "started_at": shot.started_at.isoformat() if shot.started_at else None,
                                "completed_at": shot.completed_at.isoformat() if shot.completed_at else None,
                                "progress": {
                                    "shot_number": shot.shot_number,
                                    "status": shot_status_str,
                                    "provider_status": shot.provider_status,
                                },
                                "timestamp": now_iso,
                            }
                            yield {
                                "event": "generation_progress",
                                "data": json.dumps(shot_event),
                            }

                        last_shot_states[shot_key] = shot_status_str

                    # Check for job state transitions (e.g. CANCEL_REQUESTED, CANCELLED)
                    for job in detail.jobs:
                        job_key = str(job.id)
                        job_status_str = str(job.status)
                        prev_job_status = last_job_states.get(job_key)

                        if prev_job_status is not None and prev_job_status != job_status_str:
                            job_event = {
                                "event_type": "JOB_UPDATE",
                                "project_id": str(project_id),
                                "job_id": job_key,
                                "job_type": str(job.job_type),
                                "status": job_status_str,
                                "previous_status": prev_job_status,
                                "error": job.error_message,
                                "timestamp": now_iso,
                            }
                            yield {
                                "event": "generation_progress",
                                "data": json.dumps(job_event),
                            }

                        last_job_states[job_key] = job_status_str

                    # Build high-fidelity state signature tracking shot progress & pipeline stages
                    signature = (
                        f"{detail.stage}:"
                        f"{detail.progress_percent}:"
                        f"{detail.current_stage_label}:"
                        f"{[(s.id, s.status, s.video_path is not None) for s in detail.shots]}:"
                        f"{[(j.id, j.status) for j in detail.jobs]}:"
                        f"{detail.narration_path is not None}:"
                        f"{detail.final_video_path is not None}"
                    )

                    # Send initial or changed state immediately
                    if signature != last_signature:
                        last_signature = signature
                        yield {
                            "event": "project_update",
                            "data": detail.model_dump_json(),
                        }
                    else:
                        # Send periodic heartbeat so client connection stays alive
                        yield {
                            "event": "ping",
                            "data": json.dumps({"timestamp": now_iso}),
                        }

            except Exception:
                # Connection or query error; break loop gracefully
                break

            await asyncio.sleep(1.0)

    return EventSourceResponse(event_generator())
