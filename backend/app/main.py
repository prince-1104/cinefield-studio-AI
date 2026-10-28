"""AI Ad Film Studio – FastAPI application."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.config import settings


def create_app() -> FastAPI:
    """Application factory."""
    application = FastAPI(
        title="AI Ad Film Studio",
        version="0.1.0",
        docs_url="/api/docs",
        openapi_url="/api/openapi.json",
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
