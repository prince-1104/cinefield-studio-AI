"""Verification script and tests for data layer models and schemas."""

import asyncio
from sqlalchemy import select
from sqlalchemy.orm import selectinload

from app.database import async_session_factory
from app.models import Job, JobStatus, JobType, Project, ProjectStage, Shot, ShotStatus
from app.schemas import ProjectDetail, ProjectSummary


async def run_data_layer_verification() -> None:
    async with async_session_factory() as session:
        # 1. Create a project
        project = Project(
            product_name="Aura Glow",
            brief="Next-gen smart LED light strip that syncs with music.",
            audience="Gamers, tech enthusiasts, interior designers",
            tone="cinematic, energetic, modern",
            cta="Illuminate your space — Order Aura Glow today.",
            stage=ProjectStage.BRIEF,
        )
        session.add(project)
        await session.commit()
        await session.refresh(project)
        project_id = project.id

        # 2. Add 3 storyboard shots
        for i in range(1, 4):
            shot = Shot(
                project_id=project_id,
                shot_number=i,
                description=f"Shot {i} action sequence",
                visual_prompt=f"Cinematic 4K shot of Aura Glow in room {i}",
                narration_text=f"Experience the vibrant light of Aura Glow part {i}.",
                status=ShotStatus.PENDING,
            )
            session.add(shot)

        # 3. Add a job
        job = Job(
            project_id=project_id,
            job_type=JobType.PLAN_SCRIPT,
            status=JobStatus.QUEUED,
            payload={"brief": "Aura Glow brief"},
        )
        session.add(job)
        await session.commit()

        # 4. Query back with eager loaded relationships
        stmt = (
            select(Project)
            .where(Project.id == project_id)
            .options(selectinload(Project.shots), selectinload(Project.jobs))
        )
        result = await session.execute(stmt)
        fetched_project = result.scalar_one()

        assert fetched_project.product_name == "Aura Glow"
        assert len(fetched_project.shots) == 3
        assert len(fetched_project.jobs) == 1
        assert fetched_project.shots[0].shot_number == 1
        assert fetched_project.jobs[0].job_type == JobType.PLAN_SCRIPT

        # 5. Validate serialization to Pydantic schemas
        summary = ProjectSummary.model_validate(fetched_project)
        assert summary.product_name == "Aura Glow"
        assert summary.stage == "BRIEF"

        detail = ProjectDetail.model_validate(fetched_project)
        assert detail.product_name == "Aura Glow"
        assert len(detail.shots) == 3
        assert len(detail.jobs) == 1
        assert detail.shots[0].shot_number == 1
        assert detail.jobs[0].job_type == "PLAN_SCRIPT"

        # 6. Test updating stage and shot status
        fetched_project.stage = ProjectStage.SCRIPT
        fetched_project.shots[0].status = ShotStatus.DONE
        fetched_project.shots[0].video_path = "/data/artifacts/shot1.mp4"
        await session.commit()

        # 7. Clean up (Cascade delete)
        await session.delete(fetched_project)
        await session.commit()

        # Confirm shots and jobs were cascade deleted
        shots_remaining = await session.execute(
            select(Shot).where(Shot.project_id == project_id)
        )
        jobs_remaining = await session.execute(
            select(Job).where(Job.project_id == project_id)
        )
        assert len(shots_remaining.scalars().all()) == 0
        assert len(jobs_remaining.scalars().all()) == 0

        print(
            "Data layer verification PASSED! All models, relationships, schemas, and cascade deletes verified."
        )


if __name__ == "__main__":
    asyncio.run(run_data_layer_verification())

