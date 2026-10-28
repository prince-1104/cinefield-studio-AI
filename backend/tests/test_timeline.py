"""Tests for the canonical timeline schema, persistence service, and FFmpeg rendering."""

import asyncio
import os
import shutil
import tempfile
import uuid
from pathlib import Path

import pytest
import pytest_asyncio
from sqlalchemy.ext.asyncio import AsyncSession

from app.database import async_session_factory
from app.models.job import Job, JobStatus, JobType
from app.models.project import Project, ProjectStage
from app.models.shot import Shot, ShotStatus
from app.models.timeline_edit import TimelineEdit
from app.schemas.timeline import (
    TimelineAudio,
    TimelineCaption,
    TimelineClip,
    TimelineData,
    TimelineOverlay,
    TimelineSettings,
)
from app.services import timeline_service
from worker.ffmpeg_renderer import FFmpegMediaRenderer, inspect_rendered_video


@pytest.mark.asyncio
async def test_timeline_schema_validation():
    """Verify that the TimelineData schema enforces bounds and computes durations."""
    clip1 = TimelineClip(
        shot_number=1,
        source_path="/data/test/shot1.mp4",
        source_duration=6.0,
        source_start=1.0,
        source_end=5.5,
    )
    assert clip1.duration == 4.5

    # Out of bounds trim auto-normalization
    clip2 = TimelineClip(
        shot_number=2,
        source_path="/data/test/shot2.mp4",
        source_duration=5.0,
        source_start=3.0,
        source_end=1.0,  # Invalid: end < start
    )
    assert clip2.source_end >= clip2.source_start
    assert clip2.duration > 0

    timeline = TimelineData(
        settings=TimelineSettings(duration_target_seconds=30, aspect_ratio="16:9"),
        video_clips=[clip1, clip2],
    )
    assert timeline.total_duration == round(clip1.duration + clip2.duration, 2)


@pytest.mark.asyncio
async def test_timeline_service_get_and_save():
    """Verify bootstrapping default timeline and saving versioned edits."""
    async with async_session_factory() as db_session:
        # 1. Create a project with shots and assets
        project = Project(
            product_name="Apex Cinema",
            brief="Cinematic sports car ad.",
            audience="Auto enthusiasts",
            tone="dramatic",
            cta="Drive the Future",
            target_duration=15,
            shot_count=2,
            aspect_ratio="16:9",
            stage=ProjectStage.VIDEOS,
        )
        db_session.add(project)
        await db_session.flush()

        shot1 = Shot(
            project_id=project.id,
            shot_number=1,
            start_time=0.0,
            end_time=5.0,
            target_duration=5.0,
            actual_duration=5.0,
            description="Speeding through desert",
            visual_prompt="Sports car in desert",
            narration_text="Feel the velocity.",
            video_path="/data/artifacts/shot1.mp4",
            status=ShotStatus.DONE,
        )
        shot2 = Shot(
            project_id=project.id,
            shot_number=2,
            start_time=5.0,
            end_time=10.0,
            target_duration=5.0,
            actual_duration=5.0,
            description="Braking at sunset",
            visual_prompt="Close up of brakes",
            narration_text="Engineered for perfection.",
            video_path="/data/artifacts/shot2.mp4",
            status=ShotStatus.DONE,
        )
        db_session.add_all([shot1, shot2])
        await db_session.flush()

        # 2. Bootstrap default timeline
        t_edit = await timeline_service.get_or_create_default_timeline(db_session, project)
        assert t_edit.version == 1
        assert t_edit.is_current is True
        data = t_edit.timeline_data
        assert len(data["video_clips"]) == 2
        assert len(data["captions"]) == 2
        assert data["video_clips"][0]["shot_number"] == 1

        # 3. Save modified version 2 (reordered clips)
        timeline_model = TimelineData.model_validate(data)
        timeline_model.video_clips.reverse()
        t_edit_v2 = await timeline_service.save_timeline_edit(
            db_session, project.id, timeline_model
        )
        assert t_edit_v2.version == 2
        assert t_edit_v2.is_current is True

        # Check history
        history = await timeline_service.get_timeline_history(db_session, project.id)
        assert len(history) == 2
        assert history[0].version == 2
        assert history[1].version == 1

        # 4. Queue export
        job = await timeline_service.queue_timeline_export(
            db_session, project.id, t_edit_v2.id
        )
        assert job.job_type == JobType.ASSEMBLE
        assert job.status == JobStatus.QUEUED
        assert job.payload["timeline_edit_id"] == str(t_edit_v2.id)
        assert project.stage == ProjectStage.RENDERING


@pytest.mark.asyncio
async def test_ffmpeg_timeline_rendering_e2e(tmp_path: Path):
    """End-to-end test verifying that FFmpeg compiles a timeline with trimming and overlays into a valid MP4."""
    # 1. Generate synthetic source media using FFmpeg
    clip1 = str(tmp_path / "clip1.mp4")
    clip2 = str(tmp_path / "clip2.mp4")
    narration = str(tmp_path / "narration.wav")
    music = str(tmp_path / "music.mp3")
    logo = str(tmp_path / "logo.png")
    output = str(tmp_path / "rendered_export.mp4")

    # Generate 4s test video clip 1 (blue)
    proc1 = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=blue:s=1280x720:d=4.0",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", clip1,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    await proc1.communicate()

    # Generate 4s test video clip 2 (red)
    proc2 = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=red:s=1280x720:d=4.0",
        "-c:v", "libx264", "-pix_fmt", "yuv420p", clip2,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    await proc2.communicate()

    # Generate 5s synthetic sine tone audio for narration
    proc_narr = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=440:duration=5.0",
        "-c:a", "pcm_s16le", narration,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    await proc_narr.communicate()

    # Generate 6s synthetic music tone
    proc_music = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-f", "lavfi", "-i", "sine=frequency=220:duration=6.0",
        "-c:a", "mp3", music,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    await proc_music.communicate()

    # Generate test logo PNG with transparency
    proc_logo = await asyncio.create_subprocess_exec(
        "ffmpeg", "-y", "-f", "lavfi", "-i", "color=c=green:s=100x100:d=1.0",
        "-frames:v", "1", logo,
        stdout=asyncio.subprocess.PIPE, stderr=asyncio.subprocess.PIPE,
    )
    await proc_logo.communicate()

    # 2. Build canonical timeline data with trims:
    # Clip 1 trimmed: 0.5s to 3.0s (duration = 2.5s)
    # Clip 2 trimmed: 1.0s to 3.5s (duration = 2.5s)
    # Total expected timeline duration = 5.0s
    timeline_data = {
        "settings": {
            "duration_target_seconds": 5,
            "aspect_ratio": "16:9",
            "fps": 24,
            "width": 1920,
            "height": 1080,
        },
        "video_clips": [
            {
                "id": str(uuid.uuid4()),
                "shot_number": 1,
                "source_path": clip1,
                "source_duration": 4.0,
                "source_start": 0.5,
                "source_end": 3.0,
                "timeline_start": 0.0,
                "duration": 2.5,
                "volume": 1.0,
                "transition": "Cut",
            },
            {
                "id": str(uuid.uuid4()),
                "shot_number": 2,
                "source_path": clip2,
                "source_duration": 4.0,
                "source_start": 1.0,
                "source_end": 3.5,
                "timeline_start": 2.5,
                "duration": 2.5,
                "volume": 1.0,
                "transition": "Cut",
            },
        ],
        "overlays": [
            {
                "id": str(uuid.uuid4()),
                "asset_type": "logo",
                "asset_path": logo,
                "timeline_start": 0.0,
                "timeline_end": 5.0,
                "position": "top_right",
                "scale": 1.0,
                "opacity": 0.9,
            }
        ],
        "audio_tracks": [
            {
                "id": str(uuid.uuid4()),
                "track_type": "narration",
                "source_path": narration,
                "timeline_start": 0.0,
                "duration": 5.0,
                "volume": 1.0,
            },
            {
                "id": str(uuid.uuid4()),
                "track_type": "music",
                "source_path": music,
                "timeline_start": 0.0,
                "duration": 5.0,
                "volume": 0.2,
                "fade_in": 0.5,
                "fade_out": 0.5,
                "ducking": True,
            },
        ],
        "captions": [
            {
                "id": str(uuid.uuid4()),
                "text": "Pexyl Studio Custom Video Engine",
                "timeline_start": 0.5,
                "timeline_end": 4.5,
                "font_size": 28,
                "font_color": "#ffffff",
                "position": "bottom",
            }
        ],
    }

    # 3. Render via FFmpegMediaRenderer
    renderer = FFmpegMediaRenderer()
    rendered_file = await renderer.render_timeline(timeline_data, output)

    assert os.path.isfile(rendered_file)
    assert os.path.getsize(rendered_file) > 1000

    # 4. Verify with ffprobe
    meta = await inspect_rendered_video(rendered_file)
    assert meta["width"] == 1920
    assert meta["height"] == 1080
    assert meta["vcodec"] == "h264"
    assert meta["acodec"] == "aac"
    assert abs(meta["duration"] - 5.0) < 0.5
