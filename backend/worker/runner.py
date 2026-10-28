"""Background job worker process.

Continuously polls the PostgreSQL jobs table, claims queued work, and executes
creative planning, video generation, TTS narration, and assembly tasks
while persisting stage transitions and error state.
"""

import asyncio
import logging
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
from app.interfaces.speech_provider import SpeechProvider
from app.interfaces.video_generator import VideoGenerationProvider
from app.models.job import Job, JobStatus, JobType
from app.models.project import Project, ProjectStage
from app.models.shot import Shot, ShotStatus
from worker.gemini_planner import GeminiPlanner
from worker.local_store import LocalArtifactStorage
from worker.omni_video import GeminiOmniVideoGenerator
from worker.openai_tts import OpenAISpeechProvider

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] [worker] %(message)s",
)
logger = logging.getLogger(__name__)


class JobRunner:
    """Manages claiming and dispatching background jobs."""

    def __init__(
        self,
        planner: CreativePlanner | None = None,
        video_generator: VideoGenerationProvider | None = None,
        speech_provider: SpeechProvider | None = None,
        storage: LocalArtifactStorage | None = None,
        poll_interval_seconds: float = 2.0,
    ) -> None:
        self.planner = planner or GeminiPlanner()
        self.video_generator = video_generator or GeminiOmniVideoGenerator()
        self.speech_provider = speech_provider or OpenAISpeechProvider()
        self.storage = storage or LocalArtifactStorage()
        self.poll_interval = poll_interval_seconds
        self.running = False

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
                await session.commit()
                logger.info(f"Successfully finished job {job.id} ({job.job_type.value})")

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
                                s.error_message = str(exc)
                                break

                    await err_session.commit()

    async def _handle_plan_script(
        self,
        session: Any,
        job: Job,
        project: Project,
        payload: dict[str, Any],
    ) -> None:
        """Call CreativePlanner and populate storyboard shots."""
        storyboard = await self.planner.plan_storyboard(
            product_name=payload.get("product_name", project.product_name),
            brief=payload.get("brief", project.brief),
            audience=payload.get("audience", project.audience),
            tone=payload.get("tone", project.tone),
            cta=payload.get("cta", project.cta),
            product_image_path=payload.get(
                "product_image_path", project.product_image_path
            ),
        )

        project.script = storyboard.script_summary

        # Delete any existing shots if re-planning
        for old_shot in list(project.shots):
            await session.delete(old_shot)
        await session.flush()

        # Insert exactly 3 storyboard shots
        for s in storyboard.shots:
            shot = Shot(
                project_id=project.id,
                shot_number=s.shot_number,
                description=s.description,
                visual_prompt=s.visual_prompt,
                narration_text=s.narration_text,
                status=ShotStatus.PENDING,
                retry_count=0,
            )
            session.add(shot)

        project.stage = ProjectStage.SCRIPT
        job.result = storyboard.model_dump()

    async def _handle_generate_video(
        self,
        session: Any,
        job: Job,
        project: Project,
        payload: dict[str, Any],
    ) -> None:
        """Generate a video clip for a specific shot."""
        shot_id_str = payload.get("shot_id")
        if not shot_id_str:
            raise ValueError("Payload missing required 'shot_id'")

        shot_id = uuid.UUID(shot_id_str)
        shot = next((s for s in project.shots if s.id == shot_id), None)
        if not shot:
            raise ValueError(f"Shot {shot_id} not found in project {project.id}")

        shot.status = ShotStatus.GENERATING
        await session.flush()

        clip_dir = (
            Path(settings.ARTIFACT_DIR)
            / "projects"
            / str(project.id)
            / "clips"
        )
        clip_dir.mkdir(parents=True, exist_ok=True)
        clip_path = str(clip_dir / f"shot_{shot.shot_number}.mp4")

        # Generate clip using the configured VideoGenerationProvider
        result_path = await self.video_generator.generate_clip(
            prompt=shot.visual_prompt,
            output_path=clip_path,
            reference_image_path=payload.get("product_image_path"),
            duration_seconds=5,
        )

        shot.video_path = result_path
        shot.status = ShotStatus.DONE
        shot.error_message = None

        # Check if all 3 shots are done
        all_done = all(
            s.status == ShotStatus.DONE for s in project.shots if s.id != shot.id
        )
        if all_done:
            project.stage = ProjectStage.VIDEOS

        job.result = {"shot_id": str(shot.id), "video_path": result_path}

    async def _handle_generate_tts(
        self,
        session: Any,
        job: Job,
        project: Project,
        payload: dict[str, Any],
    ) -> None:
        """Synthesize voiceover narration using SpeechProvider."""
        text = payload.get("text")
        if not text:
            # Fallback to concatenating shot narration
            text = " ".join([s.narration_text for s in project.shots if s.narration_text])
        if not text and project.script:
            text = project.script

        audio_dir = (
            Path(settings.ARTIFACT_DIR)
            / "projects"
            / str(project.id)
            / "audio"
        )
        audio_dir.mkdir(parents=True, exist_ok=True)
        audio_path = str(audio_dir / "narration.mp3")

        result_path = await self.speech_provider.synthesize(
            text=text,
            output_path=audio_path,
            instructions=f"Speak in a {project.tone} tone for an advertisement.",
        )

        project.narration_path = result_path

        # If videos are also ready, move to NARRATION stage
        if project.stage in (ProjectStage.VIDEOS, ProjectStage.STORYBOARD_APPROVED):
            if all(s.status == ShotStatus.DONE for s in project.shots):
                project.stage = ProjectStage.NARRATION

        job.result = {"narration_path": result_path}

    async def _handle_assemble(
        self,
        session: Any,
        job: Job,
        project: Project,
        payload: dict[str, Any],
    ) -> None:
        """Delegate assembly (fully implemented in Phase P5)."""
        logger.info(f"Assembly placeholder for project {project.id}")
        job.result = {"message": "Assembly queued (ready for P5 FFmpeg renderer)"}

    async def start(self) -> None:
        """Run the worker polling loop."""
        self.running = True
        logger.info("Background JobRunner started, listening for queued jobs...")

        while self.running:
            try:
                job = await self.claim_next_job()
                if job:
                    await self.execute_job(job.id)
                else:
                    await asyncio.sleep(self.poll_interval)
            except asyncio.CancelledError:
                logger.info("Worker loop cancelled, stopping...")
                break
            except Exception as e:
                logger.error(f"Error in worker polling loop: {e}", exc_info=True)
                await asyncio.sleep(self.poll_interval)

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
            # On Windows signal handlers in asyncio may differ
            pass

    await runner.start()


def main() -> None:
    try:
        asyncio.run(run_worker())
    except KeyboardInterrupt:
        logger.info("Worker terminated by user")


if __name__ == "__main__":
    main()
