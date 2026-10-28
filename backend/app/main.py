"""AI Ad Film Studio – FastAPI application."""

from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings
from app.database import engine


@asynccontextmanager
async def lifespan(application: FastAPI):
    """Startup / shutdown lifecycle hook."""
    # Engine is already created at import time; nothing to initialise here
    # but the hook is the right place for future startup tasks.
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

    @application.get("/api/health")
    async def health() -> dict:
        return {"status": "ok", "service": "ad-film-studio-api"}

    return application


app = create_app()
