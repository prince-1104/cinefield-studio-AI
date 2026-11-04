"""AI Ad Film Studio – FastAPI application."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine, async_session_factory
from app.routers import admin, ai_creative, artifacts, cancellation, events, models, projects, timeline
from app.services.ai_usage_service import seed_default_pricing
from app.services.model_registry import model_registry


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Startup / shutdown lifecycle hook."""
    # Ensure artifacts directory exists
    Path(settings.ARTIFACT_DIR).mkdir(parents=True, exist_ok=True)
    async with async_session_factory() as session:
        try:
            await seed_default_pricing(session)
        except Exception:
            pass
    yield
    await engine.dispose()


def create_app() -> FastAPI:
    """Application factory."""
    application = FastAPI(
        title="AI Ad Film Studio",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
        lifespan=lifespan,
    )

    application.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Register routers
    application.include_router(projects.router)
    application.include_router(timeline.router)
    application.include_router(events.router)
    application.include_router(artifacts.router)
    application.include_router(ai_creative.router)
    application.include_router(admin.router)
    application.include_router(models.router)
    application.include_router(cancellation.router)

    @application.get("/api/health")
    async def health() -> dict:
        return {"status": "ok", "service": "ad-film-studio-api"}

    @application.get("/api/video-models")
    async def get_video_models() -> list[dict]:
        return [m.model_dump() for m in model_registry.list_models(capability="video_generation", include_unavailable=True)]

    return application


app = create_app()
