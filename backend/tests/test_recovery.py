"""Tests for job recovery and duplicate paid generation prevention."""

import os
import uuid
from pathlib import Path

import pytest
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import async_session_factory
from app.models.job import Job, JobStatus, JobType
from app.models.project import Project, ProjectStage
from app.models.shot import Shot, ShotStatus
from worker.runner import JobRunner


class CountingVideoGenerator:
    def __init__(self):
        self.call_count = 0

    async def generate_clip(self, **kwargs) -> str:
        self.call_count += 1
        dest = Path(kwargs["output_path"])
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"x" * 2000)
        return str(dest)


class CountingSpeechProvider:
    def __init__(self):
        self.call_count = 0

    async def synthesize(self, **kwargs) -> str:
        self.call_count += 1
        dest = Path(kwargs["output_path"])
        dest.parent.mkdir(parents=True, exist_ok=True)
        dest.write_bytes(b"x" * 1000)
        return str(dest)


async def test_recover_abandoned_jobs_with_existing_clip() -> None:
    """If worker crashed after clip was downloaded, recover_abandoned_jobs marks shot and job DONE."""
    runner = JobRunner()
    project_id = uuid.uuid4()
    shot_id = uuid.uuid4()

    # Pre-create the clip on disk simulating worker crashed right after download
    clip_dir = Path(settings.ARTIFACT_DIR) / "projects" / str(project_id) / "clips"
    clip_dir.mkdir(parents=True, exist_ok=True)
    clip_file = clip_dir / "shot_1.mp4"
    clip_file.write_bytes(b"x" * 2000)

    try:
        async with async_session_factory() as session:
            proj = Project(
                id=project_id,
                product_name="Recovery Test 1",
                brief="Testing recovery",
                audience="Testers",
                tone="Bold",
                cta="Try it",
                stage=ProjectStage.STORYBOARD_APPROVED,
            )
            session.add(proj)

            shot = Shot(
                id=shot_id,
                project_id=project_id,
                shot_number=1,
                description="Shot 1",
                visual_prompt="Visual 1",
                narration_text="Voice 1",
                status=ShotStatus.GENERATING,
            )
            session.add(shot)

            job = Job(
                project_id=project_id,
                job_type=JobType.GENERATE_VIDEO,
                status=JobStatus.RUNNING,  # Abandoned in RUNNING
                payload={"shot_id": str(shot_id)},
            )
            session.add(job)
            await session.commit()

        # Run recovery
        recovered = await runner.recover_abandoned_jobs()
        assert recovered >= 1

        # Verify state
        async with async_session_factory() as session:
            stmt = select(Job).where(Job.project_id == project_id)
            j = (await session.execute(stmt)).scalar_one()
            assert j.status == JobStatus.DONE
            assert j.result.get("recovered") is True

            s = (await session.execute(select(Shot).where(Shot.id == shot_id))).scalar_one()
            assert s.status == ShotStatus.DONE
            assert s.video_path == str(clip_file)

            # Cleanup
            await session.delete(proj)
            await session.commit()
    finally:
        if clip_file.exists():
            clip_file.unlink()


async def test_recover_abandoned_jobs_without_clip_resets_to_queued() -> None:
    """If worker crashed before clip was downloaded, recover_abandoned_jobs resets to QUEUED."""
    runner = JobRunner()
    project_id = uuid.uuid4()
    shot_id = uuid.uuid4()

    async with async_session_factory() as session:
        proj = Project(
            id=project_id,
            product_name="Recovery Test 2",
            brief="Testing recovery reset",
            audience="Testers",
            tone="Bold",
            cta="Try it",
            stage=ProjectStage.STORYBOARD_APPROVED,
        )
        session.add(proj)

        shot = Shot(
            id=shot_id,
            project_id=project_id,
            shot_number=1,
            description="Shot 1",
            visual_prompt="Visual 1",
            narration_text="Voice 1",
            status=ShotStatus.GENERATING,
        )
        session.add(shot)

        job = Job(
            project_id=project_id,
            job_type=JobType.GENERATE_VIDEO,
            status=JobStatus.RUNNING,  # Abandoned without clip file
            payload={"shot_id": str(shot_id)},
        )
        session.add(job)
        await session.commit()

    recovered = await runner.recover_abandoned_jobs()
    assert recovered >= 1

    async with async_session_factory() as session:
        stmt = select(Job).where(Job.project_id == project_id)
        j = (await session.execute(stmt)).scalar_one()
        assert j.status == JobStatus.QUEUED

        s = (await session.execute(select(Shot).where(Shot.id == shot_id))).scalar_one()
        assert s.status == ShotStatus.PENDING

        await session.delete(proj)
        await session.commit()


async def test_duplicate_paid_generation_prevention() -> None:
    """Verify runner skips calling provider when artifact already exists on disk."""
    video_gen = CountingVideoGenerator()
    tts_prov = CountingSpeechProvider()
    runner = JobRunner(video_generator=video_gen, speech_provider=tts_prov)

    project_id = uuid.uuid4()
    shot_id = uuid.uuid4()

    # Pre-create clip and audio files on disk
    clip_dir = Path(settings.ARTIFACT_DIR) / "projects" / str(project_id) / "clips"
    clip_dir.mkdir(parents=True, exist_ok=True)
    clip_file = clip_dir / "shot_1.mp4"
    clip_file.write_bytes(b"x" * 2000)

    audio_dir = Path(settings.ARTIFACT_DIR) / "projects" / str(project_id) / "audio"
    audio_dir.mkdir(parents=True, exist_ok=True)
    audio_file = audio_dir / "narration.mp3"
    audio_file.write_bytes(b"x" * 1000)

    try:
        async with async_session_factory() as session:
            proj = Project(
                id=project_id,
                product_name="Deduplication Test",
                brief="Testing duplicate prevention",
                audience="Testers",
                tone="Bold",
                cta="Try it",
                stage=ProjectStage.STORYBOARD_APPROVED,
            )
            session.add(proj)

            shot = Shot(
                id=shot_id,
                project_id=project_id,
                shot_number=1,
                description="Shot 1",
                visual_prompt="Visual 1",
                narration_text="Voice 1",
                status=ShotStatus.PENDING,
            )
            session.add(shot)

            v_job = Job(
                project_id=project_id,
                job_type=JobType.GENERATE_VIDEO,
                status=JobStatus.QUEUED,
                payload={"shot_id": str(shot_id)},
            )
            session.add(v_job)

            t_job = Job(
                project_id=project_id,
                job_type=JobType.GENERATE_TTS,
                status=JobStatus.QUEUED,
                payload={"text": "Hello audio"},
            )
            session.add(t_job)
            await session.commit()

        # Claim and execute video job
        claimed_v = await runner.claim_next_job(project_id=project_id)
        assert claimed_v is not None
        await runner.execute_job(claimed_v.id)

        # Claim and execute TTS job
        claimed_t = await runner.claim_next_job(project_id=project_id)
        assert claimed_t is not None
        await runner.execute_job(claimed_t.id)

        # Provider calls MUST BE ZERO because existing files were reused!
        assert video_gen.call_count == 0, "Video provider was called despite clip already existing!"
        assert tts_prov.call_count == 0, "TTS provider was called despite audio already existing!"

        # Verify job results indicate cached
        async with async_session_factory() as session:
            jobs = (await session.execute(select(Job).where(Job.project_id == project_id))).scalars().all()
            for j in jobs:
                assert j.status == JobStatus.DONE
                assert j.result.get("cached") is True

            await session.delete(proj)
            await session.commit()
    finally:
        if clip_file.exists():
            clip_file.unlink()
        if audio_file.exists():
            audio_file.unlink()

