"""Tests for Phase P4: Worker Loop, Gemini Omni Flash, OpenAI TTS, and Pipeline Dispatch."""

import asyncio
import tempfile
import uuid
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import async_session_factory
from app.interfaces.creative_planner import CreativePlanner
from app.interfaces.speech_provider import SpeechProvider
from app.interfaces.video_generator import VideoGenerationProvider
from app.models.job import Job, JobStatus, JobType
from app.models.project import Project, ProjectStage
from app.models.shot import Shot, ShotStatus
from app.schemas.storyboard import Storyboard, StoryboardShot
from worker.gemini_planner import GeminiPlanner
from worker.local_store import LocalArtifactStorage
from worker.omni_video import GeminiOmniVideoGenerator
from worker.openai_tts import OpenAISpeechProvider
from worker.runner import JobRunner


# ── Mock Provider Implementations for Safe Offline Testing ────────────

class MockPlanner(CreativePlanner):
    async def plan_storyboard(
        self,
        product_name: str,
        brief: str,
        audience: str,
        tone: str,
        cta: str,
        product_image_path: str | None = None,
        target_duration: int = 15,
        shot_count: int = 3,
        aspect_ratio: str = "16:9",
        **kwargs,
    ) -> Storyboard:
        return Storyboard(
            title=f"The Future of {product_name}",
            script_summary="A narrative arc taking the viewer from frustration to breakthrough.",
            full_narration="Shot 1 voice. Shot 2 voice. Shot 3 voice.",
            shots=[
                StoryboardShot(
                    shot_number=1,
                    description="Opening hook with dramatic atmosphere",
                    visual_prompt="Cinematic 4K shot of product in dramatic rain lighting",
                    narration_text="Shot 1 voice.",
                    duration_hint="5s",
                ),
                StoryboardShot(
                    shot_number=2,
                    description="Product features highlighted in action",
                    visual_prompt="Macro slow-motion tracking shot of product mechanics",
                    narration_text="Shot 2 voice.",
                    duration_hint="5s",
                ),
                StoryboardShot(
                    shot_number=3,
                    description="Emotional resolution and logo reveal",
                    visual_prompt="Sunset wide angle shot with glowing product silhouette",
                    narration_text="Shot 3 voice.",
                    duration_hint="5s",
                ),
            ],
        )


class MockVideoGenerator(VideoGenerationProvider):
    async def generate_clip(
        self,
        prompt: str,
        output_path: str,
        reference_image_path: str | None = None,
        duration_seconds: int = 5,
        aspect_ratio: str = "16:9",
    ) -> str:
        dest = Path(output_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"mock-mp4-video-bytes")
        return str(dest)


class MockSpeechProvider(SpeechProvider):
    async def synthesize(
        self,
        text: str,
        output_path: str,
        voice: str | None = None,
        instructions: str | None = None,
    ) -> str:
        dest = Path(output_path)
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"mock-mp3-narration-bytes")
        return str(dest)


class FailingVideoGenerator(VideoGenerationProvider):
    async def generate_clip(
        self,
        prompt: str,
        output_path: str,
        reference_image_path: str | None = None,
        duration_seconds: int = 5,
        aspect_ratio: str = "16:9",
    ) -> str:
        raise ConnectionError("Simulated upstream video API network timeout")


# ── Test Cases ─────────────────────────────────────────────────────────

async def test_omni_video_generator_guards() -> None:
    """Verify GeminiOmniVideoGenerator rejects unconfigured key and uses correct model ID."""
    gen = GeminiOmniVideoGenerator(api_key="")
    assert gen.model == "gemini-omni-1.1-flash"

    try:
        await gen.generate_clip(prompt="Test prompt", output_path="/tmp/test.mp4")
        assert False, "Should raise RuntimeError when key is missing"
    except RuntimeError as err:
        assert "GEMINI_API_KEY is not configured" in str(err)


async def test_openai_speech_provider_guards() -> None:
    """Verify OpenAISpeechProvider rejects unconfigured key and validates input."""
    tts = OpenAISpeechProvider(api_key="")
    assert tts.model == "gpt-4o-mini-tts"
    assert tts.voice == "coral"

    # Reject missing key
    try:
        await tts.synthesize(text="Hello world", output_path="/tmp/test.mp3")
        assert False, "Should raise RuntimeError when key is missing"
    except RuntimeError as err:
        assert "OPENAI_API_KEY is not configured" in str(err)

    # Reject empty text
    tts_with_key = OpenAISpeechProvider(api_key="sk-test")
    try:
        await tts_with_key.synthesize(text="", output_path="/tmp/test.mp3")
        assert False, "Should raise ValueError for empty text"
    except ValueError as err:
        assert "text is empty" in str(err)


async def test_job_runner_full_pipeline_dispatch() -> None:
    """Verify JobRunner processes PLAN_SCRIPT, GENERATE_VIDEO, and GENERATE_TTS jobs."""
    runner = JobRunner(
        planner=MockPlanner(),
        video_generator=MockVideoGenerator(),
        speech_provider=MockSpeechProvider(),
        storage=LocalArtifactStorage(),
    )

    async with async_session_factory() as session:
        # 1. Create initial Project
        project = Project(
            product_name="Veloce e-Bike",
            brief="Carbon fiber electric commuter bike.",
            audience="Urban commuters",
            tone="sleek, modern",
            cta="Ride the future.",
            stage=ProjectStage.BRIEF,
        )
        session.add(project)
        await session.commit()
        await session.refresh(project)
        project_id = project.id

        # 2. Enqueue PLAN_SCRIPT job
        job_plan = Job(
            project_id=project_id,
            job_type=JobType.PLAN_SCRIPT,
            status=JobStatus.QUEUED,
            payload={"product_name": "Veloce e-Bike"},
        )
        session.add(job_plan)
        await session.commit()

    # 3. Claim and execute PLAN_SCRIPT
    claimed = await runner.claim_next_job(project_id=project_id)
    assert claimed is not None
    assert claimed.job_type == JobType.PLAN_SCRIPT
    await runner.execute_job(claimed.id)

    # Verify PLAN_SCRIPT results
    async with async_session_factory() as session:
        p = (
            await session.execute(
                select(Project)
                .where(Project.id == project_id)
                .options(selectinload(Project.shots))
            )
        ).scalar_one()

        assert p.stage == ProjectStage.SCRIPT
        assert len(p.shots) == 3
        assert p.shots[0].shot_number == 1
        assert p.shots[0].status == ShotStatus.PENDING
        shot_ids = [s.id for s in p.shots]

        # 4. Enqueue 3 video jobs + 1 TTS job
        for s in p.shots:
            v_job = Job(
                project_id=project_id,
                job_type=JobType.GENERATE_VIDEO,
                status=JobStatus.QUEUED,
                payload={"shot_id": str(s.id), "shot_number": s.shot_number},
            )
            session.add(v_job)

        tts_job = Job(
            project_id=project_id,
            job_type=JobType.GENERATE_TTS,
            status=JobStatus.QUEUED,
            payload={"text": "Complete narration text"},
        )
        session.add(tts_job)
        await session.commit()

    # 5. Process the 3 video jobs and 1 TTS job
    for _ in range(4):
        claimed = await runner.claim_next_job(project_id=project_id)
        assert claimed is not None
        await runner.execute_job(claimed.id)

    # Verify all shots are DONE and project progressed
    async with async_session_factory() as session:
        p = (
            await session.execute(
                select(Project)
                .where(Project.id == project_id)
                .options(selectinload(Project.shots))
            )
        ).scalar_one()

        for shot in p.shots:
            assert shot.status == ShotStatus.DONE
            assert shot.video_path is not None
            assert Path(shot.video_path).is_file()

        assert p.narration_path is not None
        assert Path(p.narration_path).is_file()
        assert p.stage in (ProjectStage.VIDEOS, ProjectStage.NARRATION)

        # Clean up created files
        for shot in p.shots:
            if shot.video_path and Path(shot.video_path).exists():
                Path(shot.video_path).unlink()
        if p.narration_path and Path(p.narration_path).exists():
            Path(p.narration_path).unlink()

        # Clean up database record
        await session.delete(p)
        await session.commit()


async def test_job_runner_failure_handling() -> None:
    """Verify JobRunner safely captures exceptions and updates shot/job error states."""
    failing_runner = JobRunner(
        planner=MockPlanner(),
        video_generator=FailingVideoGenerator(),
        speech_provider=MockSpeechProvider(),
    )

    async with async_session_factory() as session:
        project = Project(
            product_name="Fail Test Widget",
            brief="A test widget",
            audience="Testers",
            tone="Serious",
            cta="Test now",
            stage=ProjectStage.STORYBOARD_APPROVED,
        )
        session.add(project)
        await session.commit()
        await session.refresh(project)

        shot = Shot(
            project_id=project.id,
            shot_number=1,
            description="Test shot",
            visual_prompt="Prompt that fails",
            status=ShotStatus.PENDING,
        )
        session.add(shot)
        await session.commit()
        await session.refresh(shot)

        job = Job(
            project_id=project.id,
            job_type=JobType.GENERATE_VIDEO,
            status=JobStatus.QUEUED,
            payload={"shot_id": str(shot.id), "shot_number": 1},
        )
        session.add(job)
        await session.commit()
        job_id = job.id
        project_id = project.id
        shot_id = shot.id

    claimed = await failing_runner.claim_next_job(project_id=project_id)
    assert claimed is not None
    assert claimed.id == job_id
    await failing_runner.execute_job(claimed.id)

    # Verify failure persistence
    async with async_session_factory() as session:
        failed_job = (
            await session.execute(select(Job).where(Job.id == job_id))
        ).scalar_one()
        assert failed_job.status == JobStatus.FAILED
        assert "Simulated upstream video API network timeout" in failed_job.error_message

        failed_shot = (
            await session.execute(select(Shot).where(Shot.id == shot_id))
        ).scalar_one()
        assert failed_shot.status == ShotStatus.FAILED
        assert "Simulated upstream video API network timeout" in failed_shot.error_message

        # Clean up
        proj = (
            await session.execute(select(Project).where(Project.id == project_id))
        ).scalar_one()
        await session.delete(proj)
        await session.commit()


async def run_all() -> None:
    print("Running test_omni_video_generator_guards...")
    await test_omni_video_generator_guards()

    print("Running test_openai_speech_provider_guards...")
    await test_openai_speech_provider_guards()

    print("Running test_job_runner_full_pipeline_dispatch...")
    await test_job_runner_full_pipeline_dispatch()

    print("Running test_job_runner_failure_handling...")
    await test_job_runner_failure_handling()

    print("Phase P4 tests PASSED! Video provider, TTS provider, and JobRunner fully verified.")


if __name__ == "__main__":
    asyncio.run(run_all())
