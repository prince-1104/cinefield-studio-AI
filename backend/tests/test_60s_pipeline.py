"""Comprehensive tests for Phase 2–7: 60-Second Production, Dynamic Shot Count, and Live Progress."""

import asyncio
import os
import tempfile
import uuid
from pathlib import Path
from typing import Any

import pytest
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
from app.schemas.project import ProjectCreate
from app.schemas.storyboard import Storyboard, StoryboardShot
from app.services.project_service import update_project_progress
from worker.ffmpeg_renderer import (
    FFmpegMediaRenderer,
    get_media_duration,
    inspect_rendered_video,
)
from worker.gemini_planner import GeminiPlanner
from worker.local_store import LocalArtifactStorage
from worker.runner import JobRunner


# ── Helpers to create synthetic media for testing ─────────────────────────────

async def generate_test_clip(path: str, duration: int = 2, color: str = "blue") -> str:
    """Generate a test MP4 clip using FFmpeg testsrc."""
    dest = Path(path).resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c={color}:s=320x240:d={duration}",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        str(dest),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    await proc.communicate()
    return str(dest)


async def generate_test_narration(path: str, duration: int = 6) -> str:
    """Generate a test MP3 narration track using anullsrc."""
    dest = Path(path).resolve()
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"anullsrc=r=44100:cl=stereo",
        "-t", str(duration),
        "-c:a", "libmp3lame",
        str(dest),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd, stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE
    )
    await proc.communicate()
    return str(dest)


# ── Mock Providers for Multi-Shot Offline Testing ─────────────────────────────

class MockMultiShotPlanner(CreativePlanner):
    async def plan_storyboard(
        self,
        product_name: str,
        brief: str,
        audience: str,
        tone: str,
        cta: str,
        product_image_path: str | None = None,
        target_duration: int = 60,
        shot_count: int = 8,
        aspect_ratio: str = "16:9",
        **kwargs: Any,
    ) -> Storyboard:
        shots: list[StoryboardShot] = []
        dur_per_shot = round(float(target_duration) / shot_count, 2)
        cur = 0.0

        for i in range(1, shot_count + 1):
            end_t = round(cur + dur_per_shot, 2) if i < shot_count else float(target_duration)
            shots.append(
                StoryboardShot(
                    shot_number=i,
                    start_time=cur,
                    end_time=end_t,
                    target_duration=round(end_t - cur, 2),
                    description=f"Scene {i} in cinematic multi-shot sequence",
                    visual_prompt=f"Photorealistic 8K cinematic scene {i} with volumetric lighting",
                    camera_motion="Dynamic Dolly Track",
                    transition="Cut",
                    narration_text=f"Narration line for scene {i}.",
                )
            )
            cur = end_t

        return Storyboard(
            title=f"The Vision of {product_name}",
            script_summary=f"A calibrated {target_duration}-second cinematic arc across {shot_count} scenes.",
            target_duration=target_duration,
            total_planned_duration=float(target_duration),
            shots=shots,
            full_narration=" ".join(s.narration_text for s in shots),
        )


class MockSyntheticVideoGenerator(VideoGenerationProvider):
    async def generate_clip(
        self,
        prompt: str,
        output_path: str,
        reference_image_path: str | None = None,
        duration_seconds: int = 5,
        aspect_ratio: str = "16:9",
    ) -> str:
        return await generate_test_clip(output_path, duration=duration_seconds, color="purple")


class MockSyntheticSpeechProvider(SpeechProvider):
    async def synthesize(
        self,
        text: str,
        output_path: str,
        voice: str | None = None,
        instructions: str | None = None,
    ) -> str:
        return await generate_test_narration(output_path, duration=8)


# ── Tests ─────────────────────────────────────────────────────────────────────

async def test_eight_shot_timeline_coverage() -> None:
    """Verify that an 8-shot storyboard contiguously covers the 60-second budget with 0 gaps."""
    planner = MockMultiShotPlanner()
    storyboard = await planner.plan_storyboard(
        product_name="Pexyl.ai",
        brief="Where every story becomes a production.",
        audience="Filmmakers",
        tone="cinematic",
        cta="Launch on Pexyl.ai",
        target_duration=60,
        shot_count=8,
    )

    assert len(storyboard.shots) == 8
    assert storyboard.target_duration == 60
    assert storyboard.shots[0].start_time == 0.0
    assert storyboard.shots[-1].end_time == 60.0

    # Ensure continuity between shots
    for i in range(len(storyboard.shots) - 1):
        s_current = storyboard.shots[i]
        s_next = storyboard.shots[i + 1]
        assert s_current.end_time == s_next.start_time, (
            f"Gap or overlap detected between shot {s_current.shot_number} "
            f"({s_current.end_time}s) and shot {s_next.shot_number} ({s_next.start_time}s)"
        )


async def test_gemini_planner_normalization() -> None:
    """Verify planner normalization adjusts timeline to exact target duration."""
    planner = GeminiPlanner(api_key="mock_key")

    raw_shots = [
        StoryboardShot(
            shot_number=1,
            start_time=0.0,
            end_time=4.0,
            target_duration=4.0,
            description="Shot 1",
            visual_prompt="Prompt 1",
            narration_text="Text 1",
        ),
        StoryboardShot(
            shot_number=2,
            start_time=4.0,
            end_time=8.0,
            target_duration=4.0,
            description="Shot 2",
            visual_prompt="Prompt 2",
            narration_text="Text 2",
        ),
    ]
    raw_storyboard = Storyboard(
        title="Test",
        script_summary="Summary",
        target_duration=15,
        total_planned_duration=8.0,
        shots=raw_shots,
        full_narration="Text 1 Text 2",
    )

    normalized = planner._normalize_storyboard(raw_storyboard, target_duration=15, shot_count=3)
    assert len(normalized.shots) == 3
    assert normalized.shots[0].start_time == 0.0
    assert normalized.shots[-1].end_time == 15.0


def test_progress_calculation() -> None:
    """Verify honest pipeline progress calculation across stages."""
    project = Project(
        product_name="Apex Pulse",
        brief="Test",
        audience="Athletes",
        tone="cinematic",
        cta="Order",
        target_duration=60,
        shot_count=8,
        stage=ProjectStage.BRIEF,
    )

    update_project_progress(project)
    assert project.progress_percent == 5.0

    project.stage = ProjectStage.SCRIPT
    update_project_progress(project)
    assert project.progress_percent == 15.0

    project.stage = ProjectStage.VIDEOS
    # Create 8 shots: 4 done, 2 generating, 2 pending
    project.shots = [
        Shot(project_id=uuid.uuid4(), shot_number=i, description=f"S{i}", visual_prompt=f"P{i}",
             status=ShotStatus.DONE if i <= 4 else (ShotStatus.GENERATING if i <= 6 else ShotStatus.PENDING))
        for i in range(1, 9)
    ]
    project.narration_path = "/path/to/narration.mp3"

    update_project_progress(project)
    # Expected: 20 base + (4 + 2*0.4)/8 * 55 + 10 = 20 + 33 + 10 = 63.0%
    assert 60.0 <= project.progress_percent <= 65.0
    assert "4/8" in (project.current_stage_label or "")

    project.stage = ProjectStage.ASSEMBLED
    update_project_progress(project)
    assert project.progress_percent == 100.0


async def test_worker_arbitrary_shot_count_dispatch() -> None:
    """Verify worker can plan and process a 5-shot sequence."""
    runner = JobRunner(
        planner=MockMultiShotPlanner(),
        video_generator=MockSyntheticVideoGenerator(),
        speech_provider=MockSyntheticSpeechProvider(),
        media_renderer=FFmpegMediaRenderer(),
        storage=LocalArtifactStorage(),
    )

    async with async_session_factory() as session:
        # 1. Create project with 5 shots, 30s target
        project = Project(
            product_name="Pexyl 30s Film",
            brief="Next-gen cinematic studio.",
            audience="Creators",
            tone="cinematic, bold",
            cta="Create on Pexyl.ai",
            target_duration=30,
            shot_count=5,
            aspect_ratio="16:9",
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
            payload={
                "target_duration": 30,
                "shot_count": 5,
                "aspect_ratio": "16:9",
            },
        )
        session.add(job_plan)
        await session.commit()

    # 3. Claim and execute PLAN_SCRIPT
    claimed = await runner.claim_next_job(project_id=project_id)
    assert claimed is not None
    await runner.execute_job(claimed.id)

    async with async_session_factory() as session:
        p = (
            await session.execute(
                select(Project).where(Project.id == project_id).options(selectinload(Project.shots))
            )
        ).scalar_one()

        assert p.stage == ProjectStage.SCRIPT
        assert len(p.shots) == 5
        assert p.shots[0].shot_number == 1
        assert p.shots[4].shot_number == 5


async def test_ffmpeg_renderer_metadata_inspection() -> None:
    """Verify FFmpeg renderer creates MP4 and inspect_rendered_video records valid metadata."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)

        # Generate 4 short test clips (2s each)
        clips = [
            await generate_test_clip(str(tmp / f"clip_{i}.mp4"), duration=2, color=c)
            for i, c in enumerate(["red", "green", "blue", "orange"])
        ]
        narration = await generate_test_narration(str(tmp / "narration.mp3"), duration=8)
        out_path = str(tmp / "final_ad.mp4")

        renderer = FFmpegMediaRenderer()
        rendered = await renderer.render_advertisement(
            clip_paths=clips,
            narration_path=narration,
            output_path=out_path,
            cta_text="Where Every Story Becomes a Production",
            aspect_ratio="16:9",
            target_duration=8,
        )

        assert os.path.isfile(rendered)

        meta = await inspect_rendered_video(rendered)
        assert meta["duration"] > 0
        assert meta["width"] == 1920
        assert meta["height"] == 1080
        assert meta["vcodec"] == "h264"
        assert meta["size_bytes"] > 5000
