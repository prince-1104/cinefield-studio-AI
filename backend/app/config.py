"""Centralised configuration loaded from environment variables."""

from pydantic import field_validator
from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application settings.

    Every value can be overridden via an environment variable of the same name.
    AI model identifiers are configurable so they can be updated without code
    changes when providers rotate preview/GA model strings.
    """

    # --- Database ---
    DATABASE_URL: str = "postgresql+asyncpg://adstudio:adstudio@postgres:5432/adstudio"

    # --- CORS ---
    CORS_ORIGINS: list[str] = ["http://localhost:5173", "http://localhost:3000"]

    # --- Artifact storage ---
    ARTIFACT_DIR: str = "/data/artifacts"

    # --- Google Gemini – text planning ---
    GEMINI_API_KEY: str = ""
    GEMINI_TEXT_MODEL: str = "gemini-3.8-flash"

    # --- Google Gemini – video generation (Interactions API) ---
    GEMINI_VIDEO_MODEL: str = "gemini-omni-1.1-flash"

    # --- OpenAI – text-to-speech ---
    OPENAI_API_KEY: str = ""
    OPENAI_TTS_MODEL: str = "gpt-4o-mini-tts"
    OPENAI_TTS_VOICE: str = "coral"

    @field_validator("GEMINI_API_KEY", "OPENAI_API_KEY", mode="before")
    @classmethod
    def clean_api_keys(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip().rstrip(",")
        return v

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
