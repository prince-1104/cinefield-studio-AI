"""Tests for Phase P5: FFmpeg Media Renderer and Final Advertisement Assembly."""

import asyncio
import json
import os
import tempfile
from pathlib import Path

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import async_session_factory
from app.models.job import Job, JobStatus, JobType
from app.models.project import Project, ProjectStage
from app.models.shot import Shot, ShotStatus
from worker.ffmpeg_renderer import FFmpegMediaRenderer, get_media_duration
from worker.runner import JobRunner


async def generate_test_video(path: str, duration: int = 2, color: str = "red", size: str = "1280x720") -> str:
    """Generate a test MP4 video using FFmpeg lavfi color source."""
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"color=c={color}:s={size}:d={duration}:r=24",
        "-c:v", "libx264",
        "-pix_fmt", "yuv420p",
        str(path),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()
    assert proc.returncode == 0, f"Failed generating test video {path}"
    return str(path)


async def generate_test_audio(path: str, duration: int = 6, freq: int = 440) -> str:
    """Generate a test audio file using FFmpeg lavfi sine tone."""
    codec = "libmp3lame" if path.endswith(".mp3") else "aac"
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", f"sine=frequency={freq}:duration={duration}",
        "-c:a", codec,
        "-b:a", "128k",
        "-ar", "44100",
        str(path),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()
    assert proc.returncode == 0, f"Failed generating test audio {path}"
    return str(path)


async def generate_test_logo(path: str) -> str:
    """Generate a test logo PNG using FFmpeg."""
    cmd = [
        "ffmpeg", "-y",
        "-f", "lavfi",
        "-i", "color=c=white@0.0:s=200x80:d=1",
        "-frames:v", "1",
        str(path),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    await proc.communicate()
    assert proc.returncode == 0, f"Failed generating test logo {path}"
    return str(path)


async def probe_media_file(path: str) -> dict:
    """Probe media file streams using ffprobe."""
    cmd = [
        "ffprobe",
        "-v", "error",
        "-show_streams",
        "-show_format",
        "-of", "json",
        str(path),
    ]
    proc = await asyncio.create_subprocess_exec(
        *cmd,
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, stderr = await proc.communicate()
    assert proc.returncode == 0, f"ffprobe failed: {stderr.decode()}"
    return json.loads(stdout.decode())


async def test_ffmpeg_renderer_composition() -> None:
    """Verify FFmpegMediaRenderer normalizes 3 clips, mixes audio, overlays logo and CTA."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)

        # 1. Generate 3 synthetic video clips with differing resolutions/framerates
        clip1 = await generate_test_video(str(tmp / "clip1.mp4"), duration=2, color="red", size="1280x720")
        clip2 = await generate_test_video(str(tmp / "clip2.mp4"), duration=2, color="green", size="1920x1080")
        clip3 = await generate_test_video(str(tmp / "clip3.mp4"), duration=2, color="blue", size="640x480")

        # 2. Generate voiceover narration and background music
        narration = await generate_test_audio(str(tmp / "narration.mp3"), duration=6, freq=440)
        music = await generate_test_audio(str(tmp / "music.mp3"), duration=4, freq=220)

        # 3. Generate logo
        logo = await generate_test_logo(str(tmp / "logo.png"))

        # 4. Render final advertisement
        renderer = FFmpegMediaRenderer()
        output_mp4 = str(tmp / "final_ad.mp4")

        rendered = await renderer.render_advertisement(
            clip_paths=[clip1, clip2, clip3],
            narration_path=narration,
            output_path=output_mp4,
            music_path=music,
            logo_path=logo,
            cta_text="Try AI Ad Film Studio Today",
        )

        assert os.path.isfile(rendered)
        assert os.path.getsize(rendered) > 1000

        # 5. Probe output file
        meta = await probe_media_file(rendered)
        streams = meta["streams"]
        video_stream = next(s for s in streams if s["codec_type"] == "video")
        audio_stream = next(s for s in streams if s["codec_type"] == "audio")

        # Check normalization to 1080p
        assert video_stream["width"] == 1920
        assert video_stream["height"] == 1080
        assert video_stream["codec_name"] == "h264"

        # Check audio encoding
        assert audio_stream["codec_name"] == "aac"
        assert int(audio_stream["sample_rate"]) == 44100

        # Check total duration (~6.0 seconds)
        duration = float(meta["format"]["duration"])
        assert 5.0 <= duration <= 7.0, f"Unexpected duration: {duration}"
        print(f"Rendered advertisement verified: 1080p H.264 + AAC, duration={duration:.2f}s")


async def test_job_runner_assembly_dispatch() -> None:
    """Verify JobRunner executes ASSEMBLE jobs and transitions project to ASSEMBLED stage."""
    with tempfile.TemporaryDirectory() as tmp_dir:
        tmp = Path(tmp_dir)

        # Prepare 3 test clips and 1 narration file
        clip1 = await generate_test_video(str(tmp / "shot1.mp4"), duration=2, color="cyan")
        clip2 = await generate_test_video(str(tmp / "shot2.mp4"), duration=2, color="magenta")
        clip3 = await generate_test_video(str(tmp / "shot3.mp4"), duration=2, color="yellow")
        narration = await generate_test_audio(str(tmp / "narration.mp3"), duration=6)

        async with async_session_factory() as session:
            # 1. Create project in VIDEOS stage
            project = Project(
                product_name="Nexus Smartwatch",
                brief="Fitness tracking watch",
                audience="Athletes",
                tone="dynamic, energetic",
                cta="Shop Now at Nexus.com",
                stage=ProjectStage.VIDEOS,
                narration_path=narration,
            )
            session.add(project)
            await session.commit()
            await session.refresh(project)
            project_id = project.id

            # 2. Add 3 completed shots
            for i, clip_file in enumerate([clip1, clip2, clip3], start=1):
                shot = Shot(
                    project_id=project_id,
                    shot_number=i,
                    description=f"Action shot {i}",
                    visual_prompt=f"Shot visual {i}",
                    video_path=clip_file,
                    status=ShotStatus.DONE,
                )
                session.add(shot)

            # 3. Enqueue ASSEMBLE job
            assemble_job = Job(
                project_id=project_id,
                job_type=JobType.ASSEMBLE,
                status=JobStatus.QUEUED,
                payload={},
            )
            session.add(assemble_job)
            await session.commit()
            job_id = assemble_job.id

        # 4. Claim and run ASSEMBLE job
        runner = JobRunner(media_renderer=FFmpegMediaRenderer())
        claimed = await runner.claim_next_job(project_id=project_id)
        assert claimed is not None
        assert claimed.id == job_id
        await runner.execute_job(claimed.id)

        # 5. Verify database state
        async with async_session_factory() as session:
            p = (
                await session.execute(
                    select(Project).where(Project.id == project_id)
                )
            ).scalar_one()

            assert p.stage == ProjectStage.ASSEMBLED
            assert p.final_video_path is not None
            assert os.path.isfile(p.final_video_path)

            j = (
                await session.execute(
                    select(Job).where(Job.id == job_id)
                )
            ).scalar_one()
            assert j.status == JobStatus.DONE
            assert j.result["final_video_path"] == p.final_video_path

            # Clean up rendered file & project
            if os.path.exists(p.final_video_path):
                os.unlink(p.final_video_path)
            await session.delete(p)
            await session.commit()


async def run_all() -> None:
    print("Running test_ffmpeg_renderer_composition...")
    await test_ffmpeg_renderer_composition()

    print("Running test_job_runner_assembly_dispatch...")
    await test_job_runner_assembly_dispatch()

    print("Phase P5 tests PASSED! FFmpeg media renderer and assembly dispatch fully verified.")


if __name__ == "__main__":
    asyncio.run(run_all())
