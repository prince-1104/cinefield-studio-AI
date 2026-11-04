"""Comprehensive tests for stop/cancel generation across project, job, shot, and worker scopes."""

import io
import os
import tempfile
import uuid
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.database import async_session_factory
from app.main import app
from app.models.job import Job, JobStatus, JobType
from app.models.project import Project, ProjectStage
from app.models.shot import Shot, ShotStatus
from app.services.cancellation_service import CancellationService
from app.services.video_providers.seedance_provider import SeedanceVideoProvider
from worker.ffmpeg_renderer import FFmpegMediaRenderer
from worker.runner import JobCancelledException, JobRunner

DEFAULT_TEST_PAYLOAD = {
    "product_name": "Pexyl Cancel Test",
    "brief": "Testing project cancellation workflow",
    "audience": "Creative directors and advertisers",
    "tone": "cinematic, futuristic, bold",
    "cta": "Start creating today.",
    "target_duration": 15,
    "shot_count": 3,
    "aspect_ratio": "16:9",
}


@pytest.mark.asyncio
async def test_cancel_queued_project_generation() -> None:
    """Cancelling a project with queued jobs immediately transitions them to CANCELLED."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Create project
        create_res = await client.post("/api/projects", json=DEFAULT_TEST_PAYLOAD)
        assert create_res.status_code == 201, create_res.text
        project_id = uuid.UUID(create_res.json()["id"])

        # 2. Add queued jobs and pending shots
        async with async_session_factory() as session:
            project = await session.get(Project, project_id)
            assert project is not None

            job1 = Job(
                project_id=project_id,
                job_type=JobType.PLAN_SCRIPT,
                status=JobStatus.QUEUED,
                payload={"target_duration": 15, "shot_count": 3},
            )
            session.add(job1)
            await session.commit()

        # 3. Request cancellation
        cancel_res = await client.post(f"/api/projects/{project_id}/cancel-generation")
        assert cancel_res.status_code == 200
        data = cancel_res.json()
        assert data["project_id"] == str(project_id)
        assert data["cancelled_jobs_count"] >= 1

        # 4. Verify in DB
        async with async_session_factory() as session:
            jobs_res = await session.execute(
                select(Job).where(Job.project_id == project_id)
            )
            jobs = jobs_res.scalars().all()
            for j in jobs:
                assert j.status == JobStatus.CANCELLED
                assert j.completed_at is not None


@pytest.mark.asyncio
async def test_cancel_project_preserves_completed_shots() -> None:
    """Cancelling project generation NEVER deletes or modifies completed shots/clips."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create project
        create_res = await client.post(
            "/api/projects",
            json={
                **DEFAULT_TEST_PAYLOAD,
                "product_name": "Preserve Test",
            },
        )
        assert create_res.status_code == 201, create_res.text
        project_id = uuid.UUID(create_res.json()["id"])

        # Create dummy video file
        dummy_clip = Path(tempfile.gettempdir()) / f"test_clip_{uuid.uuid4().hex[:8]}.mp4"
        dummy_clip.write_bytes(b"\x00\x00\x00\x18ftypmp42" + b"\x00" * 2000)

        shot1_id = uuid.uuid4()
        shot2_id = uuid.uuid4()
        shot3_id = uuid.uuid4()

        async with async_session_factory() as session:
            # Shot 1: DONE
            s1 = Shot(
                id=shot1_id,
                project_id=project_id,
                shot_number=1,
                start_time=0.0,
                end_time=5.0,
                target_duration=5.0,
                actual_duration=5.0,
                description="Completed shot",
                visual_prompt="A finished car scene",
                video_path=str(dummy_clip),
                status=ShotStatus.DONE,
            )
            # Shot 2: GENERATING
            s2 = Shot(
                id=shot2_id,
                project_id=project_id,
                shot_number=2,
                start_time=5.0,
                end_time=10.0,
                target_duration=5.0,
                description="In-flight shot",
                visual_prompt="Generating scene",
                provider_job_id="task_remote_12345",
                status=ShotStatus.GENERATING,
            )
            # Shot 3: QUEUED
            s3 = Shot(
                id=shot3_id,
                project_id=project_id,
                shot_number=3,
                start_time=10.0,
                end_time=15.0,
                target_duration=5.0,
                description="Queued shot",
                visual_prompt="Awaiting scene",
                status=ShotStatus.QUEUED,
            )
            session.add_all([s1, s2, s3])
            await session.commit()

        try:
            # Call project cancel endpoint
            res = await client.post(f"/api/projects/{project_id}/cancel-generation")
            assert res.status_code == 200
            data = res.json()
            assert data["preserved_shots_count"] == 1
            assert data["cancelled_shots_count"] >= 2

            # Verify in DB
            async with async_session_factory() as session:
                shot1 = await session.get(Shot, shot1_id)
                shot2 = await session.get(Shot, shot2_id)
                shot3 = await session.get(Shot, shot3_id)

                # Shot 1 MUST be preserved as DONE with valid path
                assert shot1.status == ShotStatus.DONE
                assert shot1.video_path == str(dummy_clip)

                # Shot 2 was actively generating; flagged CANCEL_REQUESTED
                assert shot2.status == ShotStatus.CANCEL_REQUESTED

                # Shot 3 was queued; transitioned immediately to CANCELLED
                assert shot3.status == ShotStatus.CANCELLED
        finally:
            if dummy_clip.is_file():
                dummy_clip.unlink()


@pytest.mark.asyncio
async def test_cancel_single_job_endpoint() -> None:
    """POST /api/jobs/{job_id}/cancel cancels a specific background job."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # Create project
        create_res = await client.post("/api/projects", json=DEFAULT_TEST_PAYLOAD)
        assert create_res.status_code == 201
        project_id = uuid.UUID(create_res.json()["id"])

        job_id = uuid.uuid4()
        async with async_session_factory() as session:
            job = Job(
                id=job_id,
                project_id=project_id,
                job_type=JobType.ASSEMBLE,
                status=JobStatus.QUEUED,
            )
            session.add(job)
            await session.commit()

        # Cancel the specific job
        res = await client.post(f"/api/jobs/{job_id}/cancel")
        assert res.status_code == 200
        data = res.json()
        assert data["job_id"] == str(job_id)
        assert data["status"] == "CANCELLED"

        async with async_session_factory() as session:
            j = await session.get(Job, job_id)
            assert j.status == JobStatus.CANCELLED


@pytest.mark.asyncio
async def test_cancel_single_shot_generation_endpoint() -> None:
    """POST /api/shots/{shot_id}/cancel-generation cancels only that specific shot."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_res = await client.post("/api/projects", json=DEFAULT_TEST_PAYLOAD)
        assert create_res.status_code == 201
        project_id = uuid.UUID(create_res.json()["id"])

        shot_a = uuid.uuid4()
        shot_b = uuid.uuid4()
        async with async_session_factory() as session:
            s_a = Shot(
                id=shot_a,
                project_id=project_id,
                shot_number=1,
                start_time=0.0,
                end_time=5.0,
                target_duration=5.0,
                description="Shot A",
                visual_prompt="Scene A",
                status=ShotStatus.QUEUED,
            )
            s_b = Shot(
                id=shot_b,
                project_id=project_id,
                shot_number=2,
                start_time=5.0,
                end_time=10.0,
                target_duration=5.0,
                description="Shot B",
                visual_prompt="Scene B",
                status=ShotStatus.GENERATING,
            )
            session.add_all([s_a, s_b])
            await session.commit()

        # Cancel Shot A
        res = await client.post(f"/api/shots/{shot_a}/cancel-generation")
        assert res.status_code == 200
        data = res.json()
        assert data["shot_id"] == str(shot_a)
        assert data["status"] == "CANCELLED"

        # Verify Shot B remains untouched
        async with async_session_factory() as session:
            s_a_db = await session.get(Shot, shot_a)
            s_b_db = await session.get(Shot, shot_b)
            assert s_a_db.status == ShotStatus.CANCELLED
            assert s_b_db.status == ShotStatus.GENERATING


@pytest.mark.asyncio
async def test_cancel_completed_shot_returns_400() -> None:
    """Attempting to cancel an already completed shot fails with 400 Bad Request."""
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        create_res = await client.post("/api/projects", json=DEFAULT_TEST_PAYLOAD)
        assert create_res.status_code == 201
        project_id = uuid.UUID(create_res.json()["id"])

        shot_id = uuid.uuid4()
        async with async_session_factory() as session:
            s = Shot(
                id=shot_id,
                project_id=project_id,
                shot_number=1,
                start_time=0.0,
                end_time=5.0,
                target_duration=5.0,
                description="Completed shot",
                visual_prompt="Done scene",
                status=ShotStatus.DONE,
            )
            session.add(s)
            await session.commit()

        res = await client.post(f"/api/shots/{shot_id}/cancel-generation")
        assert res.status_code == 400
        assert "Completed clips are preserved" in res.json()["detail"]


@pytest.mark.asyncio
async def test_seedance_provider_cancellation_unsupported_handled_safely() -> None:
    """BytePlus Seedance API does not support remote cancellation; service handles gracefully."""
    provider = SeedanceVideoProvider()
    resp = await provider.cancel_generation("task_seedance_abc123")
    assert resp.supported is False
    assert resp.task_id == "task_seedance_abc123"
    assert "does not support remote cancellation" in resp.message


@pytest.mark.asyncio
async def test_ffmpeg_renderer_cancellation_cleans_up_tmp() -> None:
    """FFmpegMediaRenderer.cancel_render terminates processes and removes temporary files."""
    renderer = FFmpegMediaRenderer()
    out_file = Path(tempfile.gettempdir()) / f"final_{uuid.uuid4().hex[:8]}.mp4"
    dest = out_file.resolve()
    temp_dest = dest.with_suffix(".tmp.mp4")

    # Create dummy .tmp.mp4 file
    temp_dest.write_bytes(b"temporary render content")
    assert temp_dest.is_file()

    # Mock an active subprocess
    mock_proc = MagicMock()
    mock_proc.returncode = None
    mock_proc.pid = 99999
    renderer._active_processes[str(temp_dest)] = mock_proc

    # Cancel render
    cancelled = await renderer.cancel_render(str(out_file))
    assert cancelled is True
    mock_proc.terminate.assert_called_once()
    assert not temp_dest.exists(), "Temporary file must be deleted upon cancellation"


@pytest.mark.asyncio
async def test_worker_cooperative_cancellation_storyboard() -> None:
    """JobRunner aborts script planning if CANCEL_REQUESTED is detected, preserving project state."""
    runner = JobRunner()

    job_id = uuid.uuid4()
    project_id = uuid.uuid4()

    async with async_session_factory() as session:
        proj = Project(
            id=project_id,
            product_name="Cooperative Test",
            brief="Testing cooperative cancellation",
            audience="Target audience",
            tone="cinematic",
            cta="Call to action",
            target_duration=60,
            shot_count=8,
            stage=ProjectStage.BRIEF,
        )
        session.add(proj)

        job = Job(
            id=job_id,
            project_id=project_id,
            job_type=JobType.PLAN_SCRIPT,
            status=JobStatus.CANCEL_REQUESTED,  # User cancelled while in queue/start
            payload={"target_duration": 60, "shot_count": 8},
        )
        session.add(job)
        await session.commit()

    # Worker executes the job
    await runner.execute_job(job_id)

    # Verify job became CANCELLED and project stage was not corrupted
    async with async_session_factory() as session:
        j = await session.get(Job, job_id)
        p = await session.get(Project, project_id)
        assert j.status == JobStatus.CANCELLED
        assert p.stage == ProjectStage.BRIEF
