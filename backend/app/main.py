"""AI Ad Film Studio – FastAPI application."""

from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine
from app.routers import artifacts, events, projects


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Startup / shutdown lifecycle hook."""
    # Ensure artifacts directory exists
    Path(settings.ARTIFACT_DIR).mkdir(parents=True, exist_ok=True)
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
    application.include_router(events.router)
    application.include_router(artifacts.router)

    @application.get("/api/health")
    async def health() -> dict:
        return {"status": "ok", "service": "ad-film-studio-api"}

    return application


app = create_app()
