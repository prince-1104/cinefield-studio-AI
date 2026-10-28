"""Integration tests for Phase P2 API routers and services."""

import io
import uuid
from httpx import ASGITransport, AsyncClient
from sqlalchemy import select

from app.database import async_session_factory
from app.main import app
from app.models.project import Project, ProjectStage
from app.models.shot import Shot, ShotStatus


async def test_full_project_api_lifecycle() -> None:
    transport = ASGITransport(app=app)
    async with AsyncClient(transport=transport, base_url="http://test") as client:
        # 1. Health check
        res = await client.get("/api/health")
        assert res.status_code == 200
        assert res.json()["status"] == "ok"

        # 2. Create project
        create_payload = {
            "product_name": "Lumina Drone",
            "brief": "Autonomous cinematic 4K drone with obstacle avoidance.",
            "audience": "Travel vloggers and outdoor filmmakers",
            "tone": "epic, cinematic, inspiring",
            "cta": "Pre-order Lumina today.",
        }
        res = await client.post("/api/projects", json=create_payload)
        assert res.status_code == 201, res.text
        project_data = res.json()
        project_id = project_data["id"]
        assert project_data["product_name"] == "Lumina Drone"
        assert project_data["stage"] == "BRIEF"
        assert len(project_data["shots"]) == 0

        # 3. List projects
        res = await client.get("/api/projects")
        assert res.status_code == 200
        projects_list = res.json()
        assert any(p["id"] == project_id for p in projects_list)

        # 4. Get project details
        res = await client.get(f"/api/projects/{project_id}")
        assert res.status_code == 200
        assert res.json()["id"] == project_id

        # 5. Asset Uploads
        fake_image = io.BytesIO(b"\x89PNG\r\n\x1a\n\x00\x00\x00\rIHDR...")
        files = {
            "product_image": ("product.png", fake_image, "image/png"),
        }
        res = await client.post(f"/api/projects/{project_id}/uploads", files=files)
        assert res.status_code == 200
        updated = res.json()
        assert updated["product_image_path"] is not None
        assert "product_image.png" in updated["product_image_path"]

        # 6. Request script generation
        res = await client.post(f"/api/projects/{project_id}/generate-script")
        assert res.status_code == 200
        job_data = res.json()
        assert job_data["job_type"] == "PLAN_SCRIPT"
        assert job_data["status"] == "QUEUED"

        # 7. Add 3 dummy shots to project to simulate storyboard output
        async with async_session_factory() as session:
            for i in range(1, 4):
                shot = Shot(
                    project_id=uuid.UUID(project_id),
                    shot_number=i,
                    description=f"Action shot {i}",
                    visual_prompt=f"Cinematic drone flyby {i}",
                    narration_text=f"Take flight with Lumina part {i}",
                    status=ShotStatus.PENDING,
                )
                session.add(shot)
            await session.commit()

        # 8. Approve storyboard -> should enqueue 3 video jobs + 1 TTS job
        res = await client.post(f"/api/projects/{project_id}/approve")
        assert res.status_code == 200
        jobs = res.json()
        assert len(jobs) == 4  # 3 video + 1 TTS
        video_jobs = [j for j in jobs if j["job_type"] == "GENERATE_VIDEO"]
        tts_jobs = [j for j in jobs if j["job_type"] == "GENERATE_TTS"]
        assert len(video_jobs) == 3
        assert len(tts_jobs) == 1

        # Check project stage transitioned to STORYBOARD_APPROVED
        res = await client.get(f"/api/projects/{project_id}")
        assert res.json()["stage"] == "STORYBOARD_APPROVED"
        shots = res.json()["shots"]
        first_shot_id = shots[0]["id"]

        # 9. Retry a shot
        res = await client.post(f"/api/projects/{project_id}/shots/{first_shot_id}/retry")
        assert res.status_code == 200
        retry_job = res.json()
        assert retry_job["job_type"] == "GENERATE_VIDEO"

        # 10. Assemble request
        res = await client.post(f"/api/projects/{project_id}/assemble")
        assert res.status_code == 200
        assemble_job = res.json()
        assert assemble_job["job_type"] == "ASSEMBLE"

        # 11. Security: Path traversal protection on /api/artifacts
        res = await client.get("/api/artifacts/../../etc/passwd")
        assert res.status_code in (403, 404)

        # 12. Cleanup database record
        async with async_session_factory() as session:
            stmt = select(Project).where(Project.id == uuid.UUID(project_id))
            proj = (await session.execute(stmt)).scalar_one_or_none()
            if proj:
                await session.delete(proj)
                await session.commit()

        print("Phase P2 API integration test PASSED! All endpoints, uploads, and lifecycle actions verified.")


if __name__ == "__main__":
    import asyncio
    asyncio.run(test_full_project_api_lifecycle())
