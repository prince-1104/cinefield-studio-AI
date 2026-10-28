"""Server-Sent Events (SSE) router for real-time project progress streaming."""

import asyncio
import uuid
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

        while True:
            if await request.is_disconnected():
                break

            try:
                async with async_session_factory() as session:
                    project = await project_service.get_project(session, project_id)
                    if not project:
                        break

                    detail = ProjectDetail.model_validate(project)

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
                            "data": "{}",
                        }

            except Exception:
                # Connection or query error; break loop gracefully
                break

            await asyncio.sleep(1.0)

    return EventSourceResponse(event_generator())
