"""Service managing versioned, editable timeline compositions."""

import logging
import uuid
from typing import Any

from sqlalchemy import desc, select, update
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.job import Job, JobStatus, JobType
from app.models.project import Project, ProjectStage
from app.models.timeline_edit import TimelineEdit
from app.schemas.timeline import (
    TimelineAudio,
    TimelineCaption,
    TimelineClip,
    TimelineData,
    TimelineEditSummary,
    TimelineOverlay,
    TimelineSettings,
)

logger = logging.getLogger(__name__)


async def get_or_create_default_timeline(
    session: AsyncSession,
    project: Project,
) -> TimelineEdit:
    """Retrieve the current timeline edit, or bootstrap a default from project assets."""
    # 1. Check for existing current edit
    stmt = (
        select(TimelineEdit)
        .where(TimelineEdit.project_id == project.id, TimelineEdit.is_current.is_(True))
        .order_by(desc(TimelineEdit.version))
        .limit(1)
    )
    res = await session.execute(stmt)
    existing = res.scalar_one_or_none()
    if existing:
        return existing

    # 2. Check for latest edit if none marked current
    stmt_any = (
        select(TimelineEdit)
        .where(TimelineEdit.project_id == project.id)
        .order_by(desc(TimelineEdit.version))
        .limit(1)
    )
    res_any = await session.execute(stmt_any)
    latest = res_any.scalar_one_or_none()
    if latest:
        latest.is_current = True
        await session.flush()
        return latest

    # 3. Bootstrap default timeline model from generated assets
    is_portrait = project.aspect_ratio in ("9:16", "portrait")
    settings = TimelineSettings(
        duration_target_seconds=project.target_duration or 15,
        aspect_ratio="9:16" if is_portrait else "16:9",
        fps=24.0,
        width=1080 if is_portrait else 1920,
        height=1920 if is_portrait else 1080,
    )

    video_clips: list[TimelineClip] = []
    accumulated_time = 0.0

    # Explicitly query shots to prevent asyncpg lazy-load issues
    from app.models.shot import Shot
    stmt_shots = select(Shot).where(Shot.project_id == project.id).order_by(Shot.shot_number)
    res_shots = await session.execute(stmt_shots)
    sorted_shots = list(res_shots.scalars().all())

    for s in sorted_shots:
        dur = s.actual_duration or s.target_duration or 5.0
        clip = TimelineClip(
            shot_id=str(s.id),
            shot_number=s.shot_number,
            source_path=s.video_path or "",
            source_duration=round(dur, 2),
            source_start=0.0,
            source_end=round(dur, 2),
            timeline_start=round(accumulated_time, 2),
            duration=round(dur, 2),
            volume=1.0,
            transition=s.transition or "Cut",
            description=s.description,
            visual_prompt=s.visual_prompt,
        )
        video_clips.append(clip)
        accumulated_time += dur

    total_dur = round(accumulated_time, 2) or float(project.target_duration)

    overlays: list[TimelineOverlay] = []
    if project.logo_path:
        overlays.append(
            TimelineOverlay(
                asset_type="logo",
                asset_path=project.logo_path,
                timeline_start=0.0,
                timeline_end=total_dur,
                position="top_right",
                scale=1.0,
                opacity=1.0,
            )
        )

    audio_tracks: list[TimelineAudio] = []
    if project.narration_path:
        audio_tracks.append(
            TimelineAudio(
                track_type="narration",
                source_path=project.narration_path,
                timeline_start=0.0,
                duration=total_dur,
                volume=1.0,
                ducking=False,
            )
        )

    if project.music_path:
        audio_tracks.append(
            TimelineAudio(
                track_type="music",
                source_path=project.music_path,
                timeline_start=0.0,
                duration=total_dur,
                volume=0.25,
                fade_in=0.5,
                fade_out=1.0,
                ducking=True,
            )
        )

    captions: list[TimelineCaption] = []
    for s in sorted_shots:
        if s.narration_text:
            captions.append(
                TimelineCaption(
                    text=s.narration_text,
                    timeline_start=round(s.start_time, 2),
                    timeline_end=round(s.end_time, 2),
                    font_size=28,
                    font_color="#ffffff",
                    position="bottom",
                    style="standard",
                )
            )

    timeline_data = TimelineData(
        settings=settings,
        video_clips=video_clips,
        overlays=overlays,
        audio_tracks=audio_tracks,
        captions=captions,
    )

    new_edit = TimelineEdit(
        project_id=project.id,
        version=1,
        timeline_data=timeline_data.model_dump(),
        is_current=True,
        rendered_video_path=project.final_video_path,
    )
    session.add(new_edit)
    await session.flush()
    await session.refresh(new_edit)
    return new_edit


async def save_timeline_edit(
    session: AsyncSession,
    project_id: uuid.UUID,
    timeline_data: TimelineData,
) -> TimelineEdit:
    """Save a new version of the timeline, preserving immutable version history."""
    # Find max existing version
    stmt = (
        select(TimelineEdit.version)
        .where(TimelineEdit.project_id == project_id)
        .order_by(desc(TimelineEdit.version))
        .limit(1)
    )
    res = await session.execute(stmt)
    latest_ver = res.scalar_one_or_none() or 0

    # Mark existing versions as not current
    await session.execute(
        update(TimelineEdit)
        .where(TimelineEdit.project_id == project_id)
        .values(is_current=False)
    )

    # Validate and normalize timeline offsets
    accumulated = 0.0
    for clip in timeline_data.video_clips:
        clip.timeline_start = round(accumulated, 2)
        clip.duration = round(clip.source_end - clip.source_start, 2)
        accumulated += clip.duration

    new_version = latest_ver + 1
    new_edit = TimelineEdit(
        project_id=project_id,
        version=new_version,
        timeline_data=timeline_data.model_dump(),
        is_current=True,
    )
    session.add(new_edit)
    await session.flush()
    await session.refresh(new_edit)
    return new_edit


async def get_timeline_history(
    session: AsyncSession,
    project_id: uuid.UUID,
) -> list[TimelineEditSummary]:
    """Retrieve version history summaries for a project."""
    stmt = (
        select(TimelineEdit)
        .where(TimelineEdit.project_id == project_id)
        .order_by(desc(TimelineEdit.version))
    )
    res = await session.execute(stmt)
    edits = res.scalars().all()

    summaries: list[TimelineEditSummary] = []
    for e in edits:
        data = e.timeline_data or {}
        clips = data.get("video_clips", [])
        dur = sum(float(c.get("duration", 0.0)) for c in clips)
        summaries.append(
            TimelineEditSummary(
                id=e.id,
                version=e.version,
                is_current=e.is_current,
                clip_count=len(clips),
                duration=round(dur, 2),
                has_rendered_video=bool(e.rendered_video_path),
                created_at=e.created_at,
            )
        )
    return summaries


async def queue_timeline_export(
    session: AsyncSession,
    project_id: uuid.UUID,
    timeline_edit_id: uuid.UUID,
) -> Job:
    """Queue an FFmpeg render job compiling the specified timeline snapshot into an MP4."""
    # 1. Fetch project
    project = await session.get(Project, project_id)
    if not project:
        raise ValueError(f"Project {project_id} not found")

    # 2. Fetch timeline edit
    edit = await session.get(TimelineEdit, timeline_edit_id)
    if not edit or edit.project_id != project_id:
        raise ValueError(f"Timeline edit {timeline_edit_id} not found for project {project_id}")

    # 3. Create ASSEMBLE job
    job = Job(
        project_id=project_id,
        job_type=JobType.ASSEMBLE,
        status=JobStatus.QUEUED,
        payload={"timeline_edit_id": str(timeline_edit_id)},
    )
    session.add(job)
    await session.flush()

    edit.render_job_id = job.id
    project.stage = ProjectStage.RENDERING
    project.current_stage_label = f"Exporting Timeline Version {edit.version}..."
    project.progress_percent = 50.0

    await session.flush()
    await session.refresh(job)
    return job
