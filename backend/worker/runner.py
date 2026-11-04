"""Background job worker process.

Continuously polls the PostgreSQL jobs table, claims queued work, and executes
creative planning, video generation, TTS narration, and assembly tasks
while persisting stage transitions, real pipeline progress metrics, and failure recovery.
"""

import asyncio
import logging
import os
import signal
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.config import settings
from app.database import async_session_factory
from app.interfaces.creative_planner import CreativePlanner
from app.interfaces.media_renderer import MediaRenderer
from app.interfaces.speech_provider import SpeechProvider
from app.interfaces.video_generator import VideoGenerationProvider
from app.models.job import Job, JobStatus, JobType
from app.models.project import Project, ProjectStage
from app.models.shot import Shot, ShotStatus
from app.services.project_service import update_project_progress
from app.services.video_providers import provider_registry
from worker.claude_planner import ClaudePlanner
from worker.ffmpeg_renderer import (
    FFmpegMediaRenderer,
    get_media_duration,
    inspect_rendered_video,
)
from worker.gemini_planner import GeminiPlanner
from worker.local_store import LocalArtifactStorage
from worker.omni_video import GeminiOmniVideoGenerator
from worker.openai_tts import OpenAISpeechProvider

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [worker] %(message)s",
)
logger = logging.getLogger(__name__)


class JobCancelledException(Exception):
    """Raised when a background job is cancelled by user request."""


class JobRunner:
    """Manages claiming, recovering, and dispatching background jobs."""

    def __init__(
        self,
        planner: CreativePlanner | None = None,
        video_generator: VideoGenerationProvider | None = None,
        speech_provider: SpeechProvider | None = None,
        media_renderer: MediaRenderer | None = None,
        storage: LocalArtifactStorage | None = None,
        poll_interval_seconds: float = 2.0,
        max_concurrent_jobs: int | None = None,
    ) -> None:
        if planner is not None:
            self.planner = planner
        elif settings.PLANNER_PROVIDER == "claude" and settings.CLAUDE_API_KEY:
            self.planner = ClaudePlanner()
        else:
            self.planner = GeminiPlanner()

        self._custom_video_generator = video_generator
        self.video_generator = video_generator or GeminiOmniVideoGenerator()
        self.speech_provider = speech_provider or OpenAISpeechProvider()
        self.media_renderer = media_renderer or FFmpegMediaRenderer()
        self.storage = storage or LocalArtifactStorage()
        self.poll_interval = poll_interval_seconds
        self.max_concurrent_jobs = max_concurrent_jobs or settings.MAX_CONCURRENT_JOBS
        self.running = False

    async def _is_job_cancelled(self, job_id: uuid.UUID) -> bool:
        """Check if a job has been flagged as CANCEL_REQUESTED or CANCELLED."""
        try:
            async with async_session_factory() as session:
                res = await session.execute(select(Job.status).where(Job.id == job_id))
                job_status = res.scalar_one_or_none()
                return job_status in (JobStatus.CANCEL_REQUESTED, JobStatus.CANCELLED)
        except Exception as e:
            logger.warning(f"Error checking cancellation status for job {job_id}: {e}")
            return False

    async def _is_shot_cancelled(self, shot_id: uuid.UUID) -> bool:
        """Check if a shot has been flagged as CANCEL_REQUESTED or CANCELLED."""
        try:
            async with async_session_factory() as session:
                res = await session.execute(select(Shot.status).where(Shot.id == shot_id))
                shot_status = res.scalar_one_or_none()
                return shot_status in (ShotStatus.CANCEL_REQUESTED, ShotStatus.CANCELLED)
        except Exception as e:
            logger.warning(f"Error checking cancellation status for shot {shot_id}: {e}")
            return False

    async def recover_abandoned_jobs(self) -> int:
        """Find and recover jobs left in RUNNING status by a terminated or crashed worker.

        Checks if artifacts (clips, audio, final ad) already exist on disk to safely
        mark jobs DONE without re-triggering paid generation. Otherwise resets them to QUEUED.
        """
        async with async_session_factory() as session:
            stmt = (
                select(Job)
                .where(Job.status == JobStatus.RUNNING)
                .options(selectinload(Job.project).selectinload(Project.shots))
            )
            result = await session.execute(stmt)
            running_jobs = list(result.scalars().all())

            if not running_jobs:
                return 0

            logger.info(
                f"Found {len(running_jobs)} abandoned RUNNING job(s) from previous session. Recovering..."
            )
            recovered_count = 0

            for job in running_jobs:
                project = job.project
                payload = job.payload or {}

                if job.job_type == JobType.GENERATE_VIDEO:
                    shot_id_str = payload.get("shot_id")
                    shot = None
                    if shot_id_str:
                        shot_id = uuid.UUID(shot_id_str)
                        shot = next((s for s in project.shots if s.id == shot_id), None)

                    clip_path = (
                        Path(settings.ARTIFACT_DIR)
                        / "projects"
                        / str(project.id)
                        / "clips"
                        / f"shot_{shot.shot_number if shot else '1'}.mp4"
                    )

                    if clip_path.is_file() and clip_path.stat().st_size > 1000:
                        logger.info(
                            f"Clip {clip_path} exists for job {job.id}. Marking shot and job DONE."
                        )
                        if shot:
                            shot.status = ShotStatus.DONE
                            shot.video_path = str(clip_path)
                            shot.actual_duration = await get_media_duration(str(clip_path))
                            shot.error_message = None
                        job.status = JobStatus.DONE
                        job.completed_at = datetime.now(timezone.utc)
                        job.result = {
                            "shot_id": str(shot.id) if shot else None,
                            "video_path": str(clip_path),
                            "recovered": True,
                        }
                    else:
                        # Check if provider task is completed and can be retrieved
                        retrieved = False
                        if shot and shot.provider_job_id:
                            try:
                                provider, _ = provider_registry.get_provider_for_model(
                                    shot.model or settings.SEEDANCE_DEFAULT_MODEL
                                )
                                status_resp = await provider.get_generation_status(shot.provider_job_id)
                                if status_resp.status == "DONE":
                                    await provider.retrieve_generated_video(
                                        shot.provider_job_id, str(clip_path), status_resp
                                    )
                                    if clip_path.is_file() and clip_path.stat().st_size > 1000:
                                        shot.status = ShotStatus.DONE
                                        shot.video_path = str(clip_path)
                                        shot.actual_duration = await get_media_duration(str(clip_path))
                                        job.status = JobStatus.DONE
                                        job.completed_at = datetime.now(timezone.utc)
                                        job.result = {
                                            "shot_id": str(shot.id),
                                            "video_path": str(clip_path),
                                            "recovered_from_provider": True,
                                        }
                                        retrieved = True
                            except Exception as rec_err:
                                logger.warning(f"Could not retrieve task from provider on recovery: {rec_err}")

                        if not retrieved:
                            logger.info(
                                f"Clip incomplete for job {job.id}. Resetting to QUEUED."
                            )
                            if shot:
                                shot.status = ShotStatus.PENDING
                            job.status = JobStatus.QUEUED
                            job.started_at = None

                elif job.job_type == JobType.GENERATE_TTS:
                    audio_path = (
                        Path(settings.ARTIFACT_DIR)
                        / "projects"
                        / str(project.id)
                        / "audio"
                        / "narration.mp3"
                    )
                    if audio_path.is_file() and audio_path.stat().st_size > 500:
                        logger.info(
                            f"Audio {audio_path} exists for job {job.id}. Marking TTS job DONE."
                        )
                        project.narration_path = str(audio_path)
                        job.status = JobStatus.DONE
                        job.completed_at = datetime.now(timezone.utc)
                        job.result = {
                            "narration_path": str(audio_path),
                            "recovered": True,
                        }
                    else:
                        logger.info(
                            f"Audio not found for job {job.id}. Resetting job to QUEUED."
                        )
                        job.status = JobStatus.QUEUED
                        job.started_at = None

                elif job.job_type == JobType.ASSEMBLE:
                    final_path = (
                        Path(settings.ARTIFACT_DIR)
                        / "projects"
                        / str(project.id)
                        / "final"
                        / "advertisement.mp4"
                    )
                    if final_path.is_file() and final_path.stat().st_size > 5000:
                        logger.info(
                            f"Final video {final_path} exists for job {job.id}. Marking job DONE."
                        )
                        project.final_video_path = str(final_path)
                        project.video_metadata = await inspect_rendered_video(str(final_path))
                        project.stage = ProjectStage.ASSEMBLED
                        job.status = JobStatus.DONE
                        job.completed_at = datetime.now(timezone.utc)
                        job.result = {
                            "final_video_path": str(final_path),
                            "recovered": True,
                        }
                    else:
                        logger.info(
                            f"Final video incomplete for job {job.id}. Resetting job to QUEUED."
                        )
                        job.status = JobStatus.QUEUED
                        job.started_at = None

                elif job.job_type == JobType.PLAN_SCRIPT:
                    if len(project.shots) >= project.shot_count and project.script:
                        job.status = JobStatus.DONE
                        job.completed_at = datetime.now(timezone.utc)
                    else:
                        job.status = JobStatus.QUEUED
                        job.started_at = None

                update_project_progress(project)
                recovered_count += 1

            await session.commit()
            return recovered_count

    async def claim_next_job(self, project_id: uuid.UUID | None = None) -> Job | None:
        """Atomically claim the oldest queued job (optionally filtered by project) and mark it RUNNING."""
        async with async_session_factory() as session:
            stmt = select(Job).where(Job.status == JobStatus.QUEUED)
            if project_id:
                stmt = stmt.where(Job.project_id == project_id)
            stmt = stmt.order_by(Job.created_at.asc()).limit(1).with_for_update(skip_locked=True)
            result = await session.execute(stmt)
            job = result.scalar_one_or_none()
            if not job:
                return None

            job.status = JobStatus.RUNNING
            job.started_at = datetime.now(timezone.utc)
            await session.commit()
            return job

    async def execute_job(self, claimed_job_id: uuid.UUID) -> None:
        """Execute a claimed job and record completion or failure."""
        async with async_session_factory() as session:
            stmt = (
                select(Job)
                .where(Job.id == claimed_job_id)
                .options(selectinload(Job.project).selectinload(Project.shots))
            )
            job = (await session.execute(stmt)).scalar_one_or_none()
            if not job:
                logger.warning(f"Claimed job {claimed_job_id} not found during execution")
                return

            project = job.project
            payload = job.payload or {}
            logger.info(
                f"Processing job {job.id} (type={job.job_type.value}, project={project.id})"
            )

            if job.status in (JobStatus.CANCEL_REQUESTED, JobStatus.CANCELLED):
                logger.info(f"Job {job.id} was cancelled before execution. Setting status to CANCELLED.")
                job.status = JobStatus.CANCELLED
                job.completed_at = datetime.now(timezone.utc)
                job.error_message = "Cancelled by user before execution"
                update_project_progress(project)
                await session.commit()
                return

            try:
                if job.job_type == JobType.PLAN_SCRIPT:
                    await self._handle_plan_script(session, job, project, payload)
                elif job.job_type == JobType.GENERATE_VIDEO:
                    await self._handle_generate_video(session, job, project, payload)
                elif job.job_type == JobType.GENERATE_TTS:
                    await self._handle_generate_tts(session, job, project, payload)
                elif job.job_type == JobType.ASSEMBLE:
                    await self._handle_assemble(session, job, project, payload)
                else:
                    raise ValueError(f"Unknown job type: {job.job_type}")

                job.status = JobStatus.DONE
                job.completed_at = datetime.now(timezone.utc)
                job.error_message = None
                update_project_progress(project)
                await session.commit()
                logger.info(f"Successfully finished job {job.id} ({job.job_type.value})")

            except JobCancelledException as exc:
                logger.info(f"Job {job.id} execution aborted cleanly due to cancellation: {exc}")
                await session.rollback()
                async with async_session_factory() as cancel_session:
                    c_job = (
                        await cancel_session.execute(
                            select(Job)
                            .where(Job.id == claimed_job_id)
                            .options(selectinload(Job.project).selectinload(Project.shots))
                        )
                    ).scalar_one_or_none()
                    if c_job:
                        c_job.status = JobStatus.CANCELLED
                        c_job.completed_at = datetime.now(timezone.utc)
                        c_job.error_message = str(exc)

                        if c_job.job_type == JobType.GENERATE_VIDEO and "shot_id" in payload:
                            try:
                                shot_id = uuid.UUID(payload["shot_id"])
                                for s in c_job.project.shots:
                                    if s.id == shot_id and s.status != ShotStatus.DONE:
                                        s.status = ShotStatus.CANCELLED
                                        s.completed_at = datetime.now(timezone.utc)
                                        s.error_message = str(exc)
                                        break
                            except Exception as parse_err:
                                logger.warning(f"Failed to update shot status on cancellation: {parse_err}")
                        elif c_job.job_type == JobType.PLAN_SCRIPT:
                            if not c_job.project.shots:
                                c_job.project.stage = ProjectStage.BRIEF
                                c_job.project.current_stage_label = "Ready to generate storyboard"
                        elif c_job.job_type == JobType.ASSEMBLE:
                            c_job.project.stage = ProjectStage.VIDEOS
                            c_job.project.current_stage_label = "Assembly cancelled"

                        update_project_progress(c_job.project)
                        await cancel_session.commit()
                return

            except Exception as exc:
                logger.error(
                    f"Job {job.id} failed with error: {exc}",
                    exc_info=True,
                )
                await session.rollback()

                # Re-fetch in clean transaction to record failure
                async with async_session_factory() as err_session:
                    err_job = (
                        await err_session.execute(
                            select(Job)
                            .where(Job.id == claimed_job_id)
                            .options(selectinload(Job.project).selectinload(Project.shots))
                        )
                    ).scalar_one()

                    err_job.status = JobStatus.FAILED
                    err_job.completed_at = datetime.now(timezone.utc)
                    err_job.error_message = str(exc)

                    # If this was a shot video job, also mark the shot failed
                    if err_job.job_type == JobType.GENERATE_VIDEO and "shot_id" in payload:
                        shot_id = uuid.UUID(payload["shot_id"])
                        for s in err_job.project.shots:
                            if s.id == shot_id:
                                s.status = ShotStatus.FAILED
                                s.completed_at = datetime.now(timezone.utc)
                                s.error_message = str(exc)
                                break
                    elif err_job.job_type == JobType.ASSEMBLE:
                        err_job.project.stage = ProjectStage.ASSEMBLY_FAILED
                        err_job.project.current_stage_label = f"Assembly failed: {exc}"

                    update_project_progress(err_job.project)
                    await err_session.commit()

    async def _handle_plan_script(
        self,
        session: Any,
        job: Job,
        project: Project,
        payload: dict[str, Any],
    ) -> None:
        """Call CreativePlanner and populate storyboard shots matching target duration and count."""
        target_dur = int(payload.get("target_duration", project.target_duration))
        shot_count = int(payload.get("shot_count", project.shot_count))
        aspect_ratio = str(payload.get("aspect_ratio", project.aspect_ratio))

        planner_type = payload.get("planner") or settings.PLANNER_PROVIDER
        active_planner = self.planner
        if planner_type == "claude" and settings.CLAUDE_API_KEY:
            active_planner = ClaudePlanner()
        elif planner_type == "gemini" and settings.GEMINI_API_KEY:
            active_planner = GeminiPlanner()

        import inspect
        sig = inspect.signature(active_planner.plan_storyboard)
        plan_kwargs: dict[str, Any] = {
            "product_name": payload.get("product_name", project.product_name),
            "brief": payload.get("brief", project.brief),
            "audience": payload.get("audience", project.audience),
            "tone": payload.get("tone", project.tone),
            "cta": payload.get("cta", project.cta),
            "product_image_path": payload.get("product_image_path", project.product_image_path),
        }
        if "target_duration" in sig.parameters:
            plan_kwargs["target_duration"] = target_dur
        if "shot_count" in sig.parameters:
            plan_kwargs["shot_count"] = shot_count
        if "aspect_ratio" in sig.parameters:
            plan_kwargs["aspect_ratio"] = aspect_ratio

        if await self._is_job_cancelled(job.id):
            raise JobCancelledException("Storyboard planning cancelled by user before AI planner execution.")

        try:
            storyboard = await active_planner.plan_storyboard(**plan_kwargs)
        except Exception as e:
            if await self._is_job_cancelled(job.id):
                raise JobCancelledException("Storyboard planning cancelled by user during execution.")
            if active_planner != self.planner:
                logger.warning(
                    f"Active planner {planner_type} failed ({e}), falling back to default planner"
                )
                storyboard = await self.planner.plan_storyboard(**plan_kwargs)
            else:
                raise

        if await self._is_job_cancelled(job.id):
            logger.info(f"Job {job.id} was cancelled while planner was executing; discarding generated storyboard.")
            raise JobCancelledException("Storyboard planning cancelled; generated script discarded.")

        project.script = storyboard.script_summary
        project.target_duration = target_dur
        project.shot_count = len(storyboard.shots)
        project.aspect_ratio = aspect_ratio

        # Delete any existing shots if re-planning
        for old_shot in list(project.shots):
            await session.delete(old_shot)
        await session.flush()

        # Insert new storyboard shots
        for s in storyboard.shots:
            shot = Shot(
                project_id=project.id,
                shot_number=s.shot_number,
                start_time=s.start_time,
                end_time=s.end_time,
                target_duration=s.target_duration,
                description=s.description,
                visual_prompt=s.visual_prompt,
                camera_motion=s.camera_motion,
                transition=s.transition,
                narration_text=s.narration_text,
                provider=project.selected_video_provider or settings.DEFAULT_VIDEO_PROVIDER,
                model=project.selected_video_model or settings.SEEDANCE_DEFAULT_MODEL,
                status=ShotStatus.PENDING,
                retry_count=0,
            )
            session.add(shot)

        project.stage = ProjectStage.SCRIPT
        update_project_progress(project)
        job.result = storyboard.model_dump()

    async def _handle_generate_video(
        self,
        session: Any,
        job: Job,
        project: Project,
        payload: dict[str, Any],
    ) -> None:
        """Generate a video clip for a specific shot with detailed state transitions & duplicate prevention."""
        shot_id_str = payload.get("shot_id")
        if not shot_id_str:
            raise ValueError("Payload missing required 'shot_id'")

        shot_id = uuid.UUID(shot_id_str)
        shot = next((s for s in project.shots if s.id == shot_id), None)
        if not shot:
            raise ValueError(f"Shot {shot_id} not found in project {project.id}")

        clip_dir = (
            Path(settings.ARTIFACT_DIR)
            / "projects"
            / str(project.id)
            / "clips"
        )
        clip_dir.mkdir(parents=True, exist_ok=True)
        clip_path = str(clip_dir / f"shot_{shot.shot_number}.mp4")

        # Resolve provider and model from payload or project defaults
        provider_name = payload.get("provider") or shot.provider or project.selected_video_provider or settings.DEFAULT_VIDEO_PROVIDER
        model_name = payload.get("model") or shot.model or project.selected_video_model or settings.SEEDANCE_DEFAULT_MODEL

        shot.provider = provider_name
        shot.model = model_name

        # 1. Guard against duplicate generation if clip already exists and is validated
        if shot.video_path and os.path.isfile(shot.video_path) and os.path.getsize(shot.video_path) > 1000:
            logger.info(f"Shot {shot.shot_number} video already exists at {shot.video_path}; skipping paid generation.")
            shot.status = ShotStatus.DONE
            if not shot.actual_duration:
                shot.actual_duration = await get_media_duration(shot.video_path)
            self._check_all_shots_done(project)
            job.result = {"shot_id": str(shot.id), "video_path": shot.video_path, "cached": True}
            return

        if os.path.isfile(clip_path) and os.path.getsize(clip_path) > 1000:
            logger.info(f"Existing video clip file found at {clip_path}; validating and reusing.")
            shot.video_path = clip_path
            shot.status = ShotStatus.DONE
            shot.actual_duration = await get_media_duration(clip_path)
            self._check_all_shots_done(project)
            job.result = {"shot_id": str(shot.id), "video_path": clip_path, "cached": True}
            return

        dur = int(round(shot.target_duration)) if shot.target_duration > 0 else 5

        # Check cancellation before proceeding
        if await self._is_job_cancelled(job.id) or await self._is_shot_cancelled(shot.id):
            raise JobCancelledException(f"Shot #{shot.shot_number} generation cancelled before synthesis.")

        # If a custom VideoGenerationProvider was injected (e.g. in unit tests), delegate directly to it
        if self._custom_video_generator is not None:
            shot.status = ShotStatus.SUBMITTED
            update_project_progress(project)
            await session.flush()

            shot.status = ShotStatus.GENERATING
            update_project_progress(project)
            await session.flush()

            result_path = await self._custom_video_generator.generate_clip(
                prompt=shot.visual_prompt,
                output_path=clip_path,
                reference_image_path=payload.get("product_image_path"),
                duration_seconds=dur,
                aspect_ratio=project.aspect_ratio,
            )

            if await self._is_job_cancelled(job.id) or await self._is_shot_cancelled(shot.id):
                raise JobCancelledException(f"Shot #{shot.shot_number} generation cancelled after custom synthesis.")
        else:
            # Multi-provider architecture (Seedance, Gemini, etc.)
            provider, model_info = provider_registry.get_provider_for_model(model_name)
            shot.provider = provider.provider_id
            shot.model = model_info.id

            # Check cancellation before remote API submission
            if await self._is_job_cancelled(job.id) or await self._is_shot_cancelled(shot.id):
                raise JobCancelledException(f"Shot #{shot.shot_number} generation cancelled before provider submission.")

            # Step 1: Submit async task if not yet submitted
            if not shot.provider_job_id:
                shot.status = ShotStatus.SUBMITTED
                if not shot.started_at:
                    shot.started_at = datetime.now(timezone.utc)
                update_project_progress(project)
                await session.flush()

                task_resp = await provider.generate_video(
                    prompt=shot.visual_prompt,
                    duration_seconds=dur,
                    aspect_ratio=project.aspect_ratio,
                    reference_image_path=payload.get("product_image_path"),
                    model=model_name,
                )
                shot.provider_job_id = task_resp.task_id
                shot.provider_status = task_resp.status
                await session.flush()

            # Step 2: Poll status
            shot.status = ShotStatus.GENERATING
            update_project_progress(project)
            await session.flush()

            elapsed = 0.0
            status_resp = None
            while elapsed < settings.VIDEO_GENERATION_TIMEOUT:
                # Check for cancellation on each poll iteration
                if await self._is_job_cancelled(job.id) or await self._is_shot_cancelled(shot.id):
                    logger.info(f"Cancellation requested for shot #{shot.shot_number} during polling loop.")
                    if shot.provider_job_id:
                        try:
                            cancel_resp = await provider.cancel_generation(shot.provider_job_id)
                            logger.info(f"Provider cancel generation result for task {shot.provider_job_id}: {cancel_resp}")
                        except Exception as prov_err:
                            logger.warning(f"Error calling provider cancel_generation: {prov_err}")

                        # Record cancelled usage in financial ledger
                        try:
                            from app.services.ai_usage_service import AIUsageService
                            is_retry = (shot.retry_count > 0) or (job.attempt > 1)
                            await AIUsageService.record_seedance_usage(
                                session=session,
                                model=shot.model or model_name,
                                operation="video_retry" if is_retry else "video_generation",
                                duration_seconds=dur,
                                provider_task_id=shot.provider_job_id,
                                project_id=project.id,
                                shot_id=shot.id,
                                job_id=job.id,
                                request_status="CANCELLED",
                                error_code="USER_CANCELLED",
                                error_message="Generation cancelled by user while in progress",
                            )
                            await session.flush()
                        except Exception as usage_err:
                            logger.warning(f"Failed to record cancelled Seedance usage: {usage_err}")

                    raise JobCancelledException(f"Shot #{shot.shot_number} cancelled by user during remote generation.")

                status_resp = await provider.get_generation_status(shot.provider_job_id)
                shot.provider_status = status_resp.status

                if status_resp.status == "DONE":
                    break
                elif status_resp.status == "FAILED":
                    shot.status = ShotStatus.FAILED
                    shot.completed_at = datetime.now(timezone.utc)
                    shot.error_message = status_resp.error_message or "Video generation task failed"
                    update_project_progress(project)

                    try:
                        from app.services.ai_usage_service import AIUsageService
                        is_retry = (shot.retry_count > 0) or (job.attempt > 1)
                        await AIUsageService.record_seedance_usage(
                            session=session,
                            model=shot.model or model_name,
                            operation="video_retry" if is_retry else "video_generation",
                            duration_seconds=dur,
                            provider_task_id=shot.provider_job_id,
                            project_id=project.id,
                            shot_id=shot.id,
                            job_id=job.id,
                            request_status="FAILED",
                            error_code="PROVIDER_TASK_FAILED",
                            error_message=shot.error_message,
                        )
                    except Exception as usage_err:
                        logger.warning(f"Failed to record failed Seedance usage: {usage_err}")

                    await session.flush()
                    raise RuntimeError(
                        f"Provider {provider.name} task {shot.provider_job_id} failed: {shot.error_message}"
                    )

                await asyncio.sleep(settings.VIDEO_POLL_INTERVAL)
                elapsed += settings.VIDEO_POLL_INTERVAL

            if not status_resp or status_resp.status != "DONE":
                shot.status = ShotStatus.FAILED
                shot.completed_at = datetime.now(timezone.utc)
                shot.error_message = f"Video generation task timed out after {settings.VIDEO_GENERATION_TIMEOUT}s"
                update_project_progress(project)
                await session.flush()
                raise TimeoutError(
                    f"Video generation task {shot.provider_job_id} timed out after {settings.VIDEO_GENERATION_TIMEOUT}s"
                )

            # Step 3: Download video
            if await self._is_job_cancelled(job.id) or await self._is_shot_cancelled(shot.id):
                raise JobCancelledException(f"Shot #{shot.shot_number} cancelled before video download.")

            shot.status = ShotStatus.DOWNLOADING
            update_project_progress(project)
            await session.flush()

            result_path = await provider.retrieve_generated_video(
                task_id=shot.provider_job_id,
                output_path=clip_path,
                status_payload=status_resp,
            )

        # Step 4: Validate stream with ffprobe
        if await self._is_job_cancelled(job.id) or await self._is_shot_cancelled(shot.id):
            raise JobCancelledException(f"Shot #{shot.shot_number} cancelled before stream validation.")

        shot.status = ShotStatus.VALIDATING
        await session.flush()

        actual_dur = await get_media_duration(result_path)
        if actual_dur <= 0:
            if os.path.isfile(result_path) and os.path.getsize(result_path) > 0:
                logger.warning(
                    f"Clip {result_path} duration could not be measured by ffprobe. "
                    f"Falling back to target duration {shot.target_duration}s."
                )
                actual_dur = shot.target_duration
            else:
                raise RuntimeError(f"Generated clip {result_path} failed ffprobe duration validation.")

        shot.actual_duration = actual_dur
        shot.video_path = result_path
        shot.status = ShotStatus.DONE
        shot.completed_at = datetime.now(timezone.utc)
        shot.error_message = None

        # Step 5: Record successful AI usage in ledger
        try:
            from app.services.ai_usage_service import AIUsageService
            is_retry = (shot.retry_count > 0) or (job.attempt > 1)
            await AIUsageService.record_seedance_usage(
                session=session,
                model=shot.model or model_name,
                operation="video_retry" if is_retry else "video_generation",
                duration_seconds=actual_dur or dur,
                provider_task_id=shot.provider_job_id,
                project_id=project.id,
                shot_id=shot.id,
                job_id=job.id,
                request_status="SUCCESS",
            )
        except Exception as usage_err:
            logger.warning(f"Could not record Seedance video generation usage: {usage_err}")

        self._check_all_shots_done(project)
        update_project_progress(project)
        job.result = {
            "shot_id": str(shot.id),
            "video_path": result_path,
            "provider": shot.provider,
            "model": shot.model,
            "provider_job_id": shot.provider_job_id,
            "actual_duration": actual_dur,
        }

    def _check_all_shots_done(self, project: Project) -> None:
        """Advance project stage when all storyboard shots have been synthesized."""
        if project.shots and all(s.status == ShotStatus.DONE for s in project.shots):
            project.stage = ProjectStage.VIDEOS

    async def _handle_generate_tts(
        self,
        session: Any,
        job: Job,
        project: Project,
        payload: dict[str, Any],
    ) -> None:
        """Synthesize voiceover narration using SpeechProvider with duplicate generation prevention."""
        audio_dir = (
            Path(settings.ARTIFACT_DIR)
            / "projects"
            / str(project.id)
            / "audio"
        )
        audio_dir.mkdir(parents=True, exist_ok=True)
        audio_path = str(audio_dir / "narration.mp3")

        # Guard against duplicate paid TTS generation if narration was already generated
        if project.narration_path and os.path.isfile(project.narration_path) and os.path.getsize(project.narration_path) > 500:
            logger.info(f"Narration already exists at {project.narration_path}; skipping duplicate TTS call.")
            job.result = {"narration_path": project.narration_path, "cached": True}
            return

        if os.path.isfile(audio_path) and os.path.getsize(audio_path) > 500:
            logger.info(f"Existing narration file found at {audio_path}; reusing without re-billing.")
            project.narration_path = audio_path
            job.result = {"narration_path": audio_path, "cached": True}
            return

        text = payload.get("text")
        if not text:
            # Fallback to concatenating shot narration
            text = " ".join([s.narration_text for s in project.shots if s.narration_text])
        if not text and project.script:
            text = project.script

        result_path = await self.speech_provider.synthesize(
            text=text,
            output_path=audio_path,
            instructions=f"Speak in a confident, cinematic, articulate, and compelling {project.tone} tone for a broadcast advertisement.",
        )

        project.narration_path = result_path
        update_project_progress(project)

        # If videos are also ready, move to NARRATION stage
        if project.stage in (ProjectStage.VIDEOS, ProjectStage.STORYBOARD_APPROVED):
            if project.shots and all(s.status == ShotStatus.DONE for s in project.shots):
                project.stage = ProjectStage.NARRATION

        job.result = {"narration_path": result_path}

    async def _handle_assemble(
        self,
        session: Any,
        job: Job,
        project: Project,
        payload: dict[str, Any],
    ) -> None:
        """Render N clips, narration, background music, captions, brand logo, and CTA into finished MP4."""
        if await self._is_job_cancelled(job.id):
            raise JobCancelledException("Assembly cancelled by user before rendering started.")

        timeline_edit_id_str = payload.get("timeline_edit_id")
        if timeline_edit_id_str:
            from app.models.timeline_edit import TimelineEdit

            edit_id = uuid.UUID(timeline_edit_id_str)
            edit = await session.get(TimelineEdit, edit_id)
            if not edit:
                raise ValueError(f"Timeline edit {edit_id} not found")

            final_dir = (
                Path(settings.ARTIFACT_DIR)
                / "projects"
                / str(project.id)
                / "final"
            )
            final_dir.mkdir(parents=True, exist_ok=True)
            export_filename = f"advertisement_v{edit.version}.mp4"
            final_path = str(final_dir / export_filename)

            project.stage = ProjectStage.ASSEMBLING
            project.current_stage_label = f"Compiling Timeline v{edit.version} in FFmpeg..."
            project.progress_percent = 75.0
            await session.flush()

            try:
                rendered_path = await self.media_renderer.render_timeline(
                    timeline_data=edit.timeline_data,
                    output_path=final_path,
                )
            except Exception:
                if await self._is_job_cancelled(job.id):
                    await self.media_renderer.cancel_render(final_path)
                    raise JobCancelledException("Timeline assembly cancelled by user during FFmpeg render.")
                raise

            if await self._is_job_cancelled(job.id):
                await self.media_renderer.cancel_render(final_path)
                raise JobCancelledException("Timeline assembly cancelled by user.")

            metadata = await inspect_rendered_video(rendered_path)
            edit.rendered_video_path = rendered_path
            project.final_video_path = rendered_path
            project.video_metadata = metadata
            project.stage = ProjectStage.ASSEMBLED
            project.progress_percent = 100.0
            project.current_stage_label = f"Cinema Master v{edit.version} Delivered & Verified"

            job.result = {
                "final_video_path": rendered_path,
                "timeline_edit_id": str(edit.id),
                "version": edit.version,
                "metadata": metadata,
            }
            return

        sorted_shots = sorted(project.shots, key=lambda s: s.shot_number)

        if not sorted_shots:
            raise ValueError("Cannot assemble: no shots found in project")

        for s in sorted_shots:
            if s.status != ShotStatus.DONE or not s.video_path or not os.path.isfile(s.video_path):
                raise ValueError(
                    f"Cannot assemble: shot #{s.shot_number} is not DONE or video file is missing"
                )

        if not project.narration_path or not os.path.isfile(project.narration_path):
            raise ValueError("Cannot assemble: narration audio has not been generated or is missing")

        clip_paths = [s.video_path for s in sorted_shots]

        # Build timed captions from individual shot narrations
        captions: list[dict[str, Any]] = []
        for s in sorted_shots:
            if s.narration_text:
                captions.append({
                    "text": s.narration_text,
                    "start": s.start_time,
                    "end": s.end_time,
                })

        final_dir = (
            Path(settings.ARTIFACT_DIR)
            / "projects"
            / str(project.id)
            / "final"
        )
        final_dir.mkdir(parents=True, exist_ok=True)
        final_path = str(final_dir / "advertisement.mp4")

        project.stage = ProjectStage.ASSEMBLING
        project.current_stage_label = "Compiling clips, audio, overlays and captions in FFmpeg..."
        update_project_progress(project)
        await session.flush()

        try:
            rendered_path = await self.media_renderer.render_advertisement(
                clip_paths=clip_paths,
                narration_path=project.narration_path,
                output_path=final_path,
                music_path=project.music_path,
                logo_path=project.logo_path,
                cta_text=project.cta,
                captions=captions,
                aspect_ratio=project.aspect_ratio,
                target_duration=project.target_duration,
            )
        except Exception:
            if await self._is_job_cancelled(job.id):
                await self.media_renderer.cancel_render(final_path)
                raise JobCancelledException("Assembly cancelled by user during FFmpeg render.")
            raise

        if await self._is_job_cancelled(job.id):
            await self.media_renderer.cancel_render(final_path)
            raise JobCancelledException("Assembly cancelled by user.")

        # Inspect and validate the final rendered MP4 via ffprobe
        metadata = await inspect_rendered_video(rendered_path)

        project.final_video_path = rendered_path
        project.video_metadata = metadata
        project.stage = ProjectStage.ASSEMBLED
        project.progress_percent = 100.0
        project.current_stage_label = "Cinema Master Delivered & Verified"

        job.result = {
            "final_video_path": rendered_path,
            "metadata": metadata,
        }

    async def start(self) -> None:
        """Run the worker polling loop, recovering any abandoned jobs on startup."""
        self.running = True
        logger.info("Background JobRunner started, checking for abandoned jobs...")

        try:
            recovered = await self.recover_abandoned_jobs()
            if recovered > 0:
                logger.info(f"Successfully processed recovery for {recovered} abandoned job(s).")
        except Exception as e:
            logger.error(f"Error during job recovery on startup: {e}", exc_info=True)

        logger.info(f"Listening for queued jobs (concurrency limit: {self.max_concurrent_jobs})...")
        active_tasks: set[asyncio.Task] = set()

        while self.running:
            try:
                # Clean up completed tasks
                done = {t for t in active_tasks if t.done()}
                active_tasks -= done

                # Check exceptions on completed tasks for logging
                for t in done:
                    if not t.cancelled() and t.exception():
                        logger.error(f"Task raised unexpected exception: {t.exception()}")

                # If under concurrency cap, claim next available job
                if len(active_tasks) < self.max_concurrent_jobs:
                    job = await self.claim_next_job()
                    if job:
                        task = asyncio.create_task(self.execute_job(job.id))
                        active_tasks.add(task)
                        continue

                await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                logger.info("Worker loop cancelled, stopping...")
                break
            except Exception as e:
                logger.error(f"Error in worker polling loop: {e}", exc_info=True)
                await asyncio.sleep(self.poll_interval)

        # Wait for remaining active tasks on shutdown
        if active_tasks:
            logger.info(f"Waiting for {len(active_tasks)} active background task(s) to finish...")
            await asyncio.gather(*active_tasks, return_exceptions=True)

    def stop(self) -> None:
        """Signal the worker to gracefully exit."""
        self.running = False


async def run_worker() -> None:
    runner = JobRunner()

    loop = asyncio.get_running_loop()
    for sig in (signal.SIGINT, signal.SIGTERM):
        try:
            loop.add_signal_handler(sig, runner.stop)
        except NotImplementedError:
            pass

    await runner.start()


def main() -> None:
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("Worker terminated by user")


if __name__ == "__main__":
    main()
