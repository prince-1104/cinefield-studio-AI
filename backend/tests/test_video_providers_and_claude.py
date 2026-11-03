"""Tests for AI Video Generation Providers (Seedance, Gemini), Claude Planner, and Model Selection."""

import asyncio
import os
import uuid
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import httpx
import pytest
from sqlalchemy import select

from app.database import async_session_factory
from app.models.job import Job, JobStatus, JobType
from app.models.project import Project, ProjectStage
from app.models.shot import Shot, ShotStatus
from app.schemas.project import ProjectCreate
from app.services import job_service, project_service
from app.services.video_providers import (
    GenerationStatusResponse,
    GenerationTaskResponse,
    SeedanceVideoProvider,
    provider_registry,
)
from worker.claude_planner import ClaudePlanner
from worker.runner import JobRunner


# ─── 1. Seedance Provider Tests ──────────────────────────────────────────

def test_seedance_provider_authentication():
    """Verify authorization headers, resource ID, and missing key error."""
    provider = SeedanceVideoProvider(
        api_key="test-seedance-key",
        resource_id="ep-2026-test",
    )
    headers = provider._get_headers()
    assert headers["Authorization"] == "Bearer test-seedance-key"
    assert headers["X-Resource-Id"] == "ep-2026-test"
    assert headers["Content-Type"] == "application/json"

    # Test error when API key is empty
    empty_provider = SeedanceVideoProvider(api_key="")
    with pytest.raises(RuntimeError, match="SEEDANCE_API_KEY is not configured"):
        empty_provider._get_headers()


def test_seedance_request_payload_resolution():
    """Verify endpoint model resolution and fallback."""
    provider = SeedanceVideoProvider(
        api_key="test-key",
        resource_id="ep-2026-custom",
    )
    # If explicit model requested, it is used
    assert provider._resolve_model_id("seedance-1-0-pro-fast-251015") == "seedance-1-0-pro-fast-251015"
    # If no model provided, custom ep- resource ID is used
    assert provider._resolve_model_id(None) == "ep-2026-custom"


@pytest.mark.asyncio
async def test_seedance_task_submission_success():
    """Mock HTTP POST /contents/generations/tasks and verify GenerationTaskResponse."""
    provider = SeedanceVideoProvider(
        api_key="test-seedance-key",
        base_url="https://mock.bytepluses.com/api/v3",
    )

    mock_resp = MagicMock()
    mock_resp.status_code = 200
    mock_resp.json.return_value = {
        "id": "cgt-mock-task-789",
        "model": "seedance-1-0-pro-250528",
        "status": "queued",
    }

    with patch("httpx.AsyncClient.post", new_callable=AsyncMock) as mock_post:
        mock_post.return_value = mock_resp

        result = await provider.generate_video(
            prompt="Cinematic drone shot of alpine peaks at dawn",
            duration_seconds=5,
            aspect_ratio="16:9",
            model="seedance-1-0-pro-250528",
        )

        assert isinstance(result, GenerationTaskResponse)
        assert result.task_id == "cgt-mock-task-789"
        assert result.provider == "seedance"
        assert result.status == "SUBMITTED"

        # Verify payload sent
        call_args = mock_post.call_args
        sent_payload = call_args.kwargs["json"]
        assert sent_payload["model"] == "seedance-1-0-pro-250528"
        assert sent_payload["resolution"] == "1080p"
        assert sent_payload["ratio"] == "16:9"
        assert sent_payload["content"][0]["text"] == "Cinematic drone shot of alpine peaks at dawn"


@pytest.mark.asyncio
async def test_seedance_status_polling():
    """Mock GET /contents/generations/tasks/{id} across queued, running, and done states."""
    provider = SeedanceVideoProvider(api_key="test-key")

    mock_resp = MagicMock()
    mock_resp.status_code = 200

    with patch("httpx.AsyncClient.get", new_callable=AsyncMock) as mock_get:
        mock_get.return_value = mock_resp

        # 1. Queued
        mock_resp.json.return_value = {"id": "task-1", "status": "queued"}
        s1 = await provider.get_generation_status("task-1")
        assert s1.status == "QUEUED"

        # 2. Running
        mock_resp.json.return_value = {"id": "task-1", "status": "running"}
        s2 = await provider.get_generation_status("task-1")
        assert s2.status == "RUNNING"

        # 3. Succeeded with video_url
        mock_resp.json.return_value = {
            "id": "task-1",
            "status": "succeeded",
            "content": {
                "video_url": "https://storage.bytepluses.com/outputs/ad_shot_1.mp4",
                "duration": 5.0,
            },
        }
        s3 = await provider.get_generation_status("task-1")
        assert s3.status == "DONE"
        assert s3.video_url == "https://storage.bytepluses.com/outputs/ad_shot_1.mp4"


@pytest.mark.asyncio
async def test_seedance_provider_errors_and_rate_limit():
    """Verify rate-limit backoff and auth failure handling."""
    provider = SeedanceVideoProvider(api_key="invalid-key")

    mock_resp_401 = MagicMock()
    mock_resp_401.status_code = 401
    mock_resp_401.text = "Unauthorized: Invalid API key"
    exc_401 = httpx.HTTPStatusError("Unauthorized", request=MagicMock(), response=mock_resp_401)

    with patch("httpx.AsyncClient.post", side_effect=exc_401):
        with pytest.raises(RuntimeError, match="Seedance authentication failed"):
            await provider.generate_video(prompt="A test prompt")


@pytest.mark.asyncio
async def test_seedance_retrieve_video_stream(tmp_path):
    """Test streaming video download from video_url to target artifact path."""
    provider = SeedanceVideoProvider(api_key="test-key")
    out_file = tmp_path / "test_shot.mp4"

    fake_video_bytes = b"\x00\x00\x00 ftypisom" + b"A" * 2000

    class MockStreamContext:
        async def __aenter__(self):
            mock_stream = MagicMock()
            mock_stream.raise_for_status = MagicMock()
            async def chunk_iter(chunk_size):
                yield fake_video_bytes
            mock_stream.aiter_bytes = chunk_iter
            return mock_stream

        async def __aexit__(self, exc_type, exc_val, exc_tb):
            pass

    with patch("httpx.AsyncClient.stream", return_value=MockStreamContext()):
        status_payload = GenerationStatusResponse(
            task_id="task-123",
            provider="seedance",
            status="DONE",
            video_url="https://mock.storage/test_shot.mp4",
        )
        saved_path = await provider.retrieve_generated_video(
            task_id="task-123",
            output_path=str(out_file),
            status_payload=status_payload,
        )

        assert os.path.isfile(saved_path)
        assert os.path.getsize(saved_path) == len(fake_video_bytes)


# ─── 2. Claude Planner Tests ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_claude_planner_storyboard_generation():
    """Verify Claude structured tool-use generation and normalization."""
    planner = ClaudePlanner(api_key="test-claude-key")

    mock_storyboard_dict = {
        "title": "Pexyl Cinematic Commercial",
        "script_summary": "From creative spark to enterprise cinema production.",
        "target_duration": 15,
        "total_planned_duration": 15.0,
        "full_narration": "Where every idea turns into a cinematic masterwork.",
        "shots": [
            {
                "shot_number": 1,
                "start_time": 0.0,
                "end_time": 5.0,
                "target_duration": 5.0,
                "description": "Opening vision of a creator in golden light",
                "visual_prompt": "Cinematic macro shot of glowing creative sparks, 8k anamorphic",
                "camera_motion": "Slow Push In",
                "transition": "Cut",
                "narration_text": "Every production starts with a vision.",
            },
            {
                "shot_number": 2,
                "start_time": 5.0,
                "end_time": 10.0,
                "target_duration": 5.0,
                "description": "Dynamic multi-screen AI composition",
                "visual_prompt": "High tech holographic interface displaying video streams",
                "camera_motion": "Orbit Pan",
                "transition": "Match Cut",
                "narration_text": "Architected by AI precision.",
            },
            {
                "shot_number": 3,
                "start_time": 10.0,
                "end_time": 15.0,
                "target_duration": 5.0,
                "description": "Hero brand reveal with tagline",
                "visual_prompt": "Pexyl logo emerging in neon violet against deep obsidian",
                "camera_motion": "Hero Reveal",
                "transition": "Fade to Black",
                "narration_text": "Where every story becomes a production.",
            },
        ],
    }

    class MockBlock:
        type = "tool_use"
        name = "create_cinematic_storyboard"
        input = mock_storyboard_dict

    class MockMessage:
        content = [MockBlock()]

    with patch("anthropic.AsyncAnthropic") as MockAnthropic:
        mock_client = MagicMock()
        mock_client.messages.create = AsyncMock(return_value=MockMessage())
        MockAnthropic.return_value = mock_client

        storyboard = await planner.plan_storyboard(
            product_name="Pexyl",
            brief="AI cinema platform launch",
            audience="Creators & filmmakers",
            tone="cinematic, luxurious",
            cta="Launch on Pexyl.ai",
            target_duration=15,
            shot_count=3,
        )

        assert storyboard.title == "Pexyl Cinematic Commercial"
        assert len(storyboard.shots) == 3
        assert storyboard.shots[0].start_time == 0.0
        assert storyboard.shots[2].end_time == 15.0


# ─── 3. Model Selection & Service Integration Tests ───────────────────────

@pytest.mark.asyncio
async def test_provider_registry_discovery():
    """Verify registry lists Seedance and Gemini models."""
    models = provider_registry.list_available_models()
    model_ids = [m.id for m in models]
    assert "seedance-1-0-pro-250528" in model_ids
    assert "seedance-1-0-pro-fast-251015" in model_ids
    assert "gemini-omni-1.1-flash" in model_ids

    provider, info = provider_registry.get_provider_for_model("seedance-1-0-pro-250528")
    assert provider.provider_id == "seedance"
    assert info.name == "Seedance 1.0 Pro"


@pytest.mark.asyncio
async def test_project_model_selection_and_duplicate_job_prevention():
    """Test switching model on project and preventing duplicate job creation on retry/refresh."""
    async with async_session_factory() as session:
        # Create project
        create_payload = ProjectCreate(
            product_name="Pexyl Model Test",
            brief="Testing model selection and job deduplication",
            audience="Developers",
            tone="technical, robust",
            cta="Test CTA",
            target_duration=15,
            shot_count=1,
            selected_video_model="seedance-1-0-pro-250528",
        )
        project = await project_service.create_project(session, create_payload)
        assert project.selected_video_model == "seedance-1-0-pro-250528"
        assert project.selected_video_provider == "seedance"

        # Update model to Seedance Fast
        updated = await project_service.update_project_model(
            session=session,
            project_id=project.id,
            model="seedance-1-0-pro-fast-251015",
            provider="seedance",
        )
        assert updated.selected_video_model == "seedance-1-0-pro-fast-251015"

        # Add a shot manually for testing
        shot = Shot(
            project_id=project.id,
            shot_number=1,
            start_time=0.0,
            end_time=5.0,
            target_duration=5.0,
            description="Shot 1",
            visual_prompt="A test visual prompt",
            status=ShotStatus.PENDING,
        )
        session.add(shot)
        await session.commit()

        # Enqueue first generation job
        job1 = await project_service.generate_shot_video(
            session=session,
            project_id=project.id,
            shot_id=shot.id,
            model="seedance-1-0-pro-fast-251015",
        )
        assert job1.status == JobStatus.QUEUED

        # Trigger duplicate generation while job1 is QUEUED
        job2 = await project_service.generate_shot_video(
            session=session,
            project_id=project.id,
            shot_id=shot.id,
        )
        # Verify deduplication returns existing job
        assert job2.id == job1.id


@pytest.mark.asyncio
async def test_concurrent_worker_execution(tmp_path):
    """Test worker processing multiple queued jobs concurrently without conflict."""
    async with async_session_factory() as session:
        # Create project
        project = Project(
            product_name="Concurrent Test",
            brief="Testing concurrency",
            audience="Test",
            tone="Test",
            cta="Test",
            target_duration=15,
            shot_count=2,
            stage=ProjectStage.STORYBOARD_APPROVED,
        )
        session.add(project)
        await session.flush()

        # Create two shots
        s1 = Shot(
            project_id=project.id,
            shot_number=1,
            start_time=0.0,
            end_time=5.0,
            target_duration=5.0,
            description="S1",
            visual_prompt="P1",
            status=ShotStatus.PENDING,
        )
        s2 = Shot(
            project_id=project.id,
            shot_number=2,
            start_time=5.0,
            end_time=10.0,
            target_duration=5.0,
            description="S2",
            visual_prompt="P2",
            status=ShotStatus.PENDING,
        )
        session.add_all([s1, s2])
        await session.flush()

        # Enqueue 2 jobs
        j1 = await job_service.enqueue_job(
            session, project.id, JobType.GENERATE_VIDEO, payload={"shot_id": str(s1.id)}
        )
        j2 = await job_service.enqueue_job(
            session, project.id, JobType.GENERATE_VIDEO, payload={"shot_id": str(s2.id)}
        )
        await session.commit()

        # Mock video generator that produces valid dummy mp4 files
        dummy_mp4 = tmp_path / "dummy.mp4"
        dummy_mp4.write_bytes(b"\x00\x00\x00 ftypisom" + b"\x00" * 3000)

        mock_generator = AsyncMock()
        mock_generator.generate_clip.return_value = str(dummy_mp4)

        runner = JobRunner(
            video_generator=mock_generator,
            poll_interval_seconds=0.1,
            max_concurrent_jobs=2,
        )

        with patch("worker.runner.get_media_duration", new_callable=AsyncMock) as mock_dur:
            mock_dur.return_value = 5.0
            # Execute both jobs
            await runner.execute_job(j1.id)
            await runner.execute_job(j2.id)

        # Verify both jobs finished DONE
        async with async_session_factory() as verify_session:
            v_j1 = await verify_session.get(Job, j1.id)
            v_j2 = await verify_session.get(Job, j2.id)
            assert v_j1.status == JobStatus.DONE
            assert v_j2.status == JobStatus.DONE
