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

    # --- Video Generation Providers ---
    DEFAULT_VIDEO_PROVIDER: str = "seedance"

    # --- ByteDance Seedance Video Provider ---
    SEEDANCE_API_KEY: str = ""
    SEEDANCE_RESOURCE_ID: str = ""
    SEEDANCE_BASE_URL: str = "https://ark.ap-southeast.bytepluses.com/api/v3"
    SEEDANCE_DEFAULT_MODEL: str = "dreamina-seedance-2-5-260628"

    # --- Google Gemini – text planning & video ---
    GEMINI_API_KEY: str = ""
    GEMINI_TEXT_MODEL: str = "gemini-3.8-flash"
    GEMINI_VIDEO_MODEL: str = "gemini-omni-1.1-flash"

    # --- Anthropic Claude – creative planning ---
    CLAUDE_API_KEY: str = ""
    CLAUDE_MODEL: str = "claude-3-7-sonnet-20250219"
    PLANNER_PROVIDER: str = "claude"

    # --- Provider Execution Controls ---
    PROVIDER_REQUEST_TIMEOUT: float = 60.0
    VIDEO_POLL_INTERVAL: float = 5.0
    VIDEO_GENERATION_TIMEOUT: float = 600.0
    MAX_CONCURRENT_JOBS: int = 4
    MAX_RETRY_LIMIT: int = 3

    # --- OpenAI – text-to-speech ---
    OPENAI_API_KEY: str = ""
    OPENAI_TTS_MODEL: str = "gpt-4o-mini-tts"
    OPENAI_TTS_VOICE: str = "coral"

    # --- Security & Admin ---
    ADMIN_API_KEY: str = "pexyl-admin-secret-2026"

    @field_validator(
        "GEMINI_API_KEY",
        "OPENAI_API_KEY",
        "SEEDANCE_API_KEY",
        "SEEDANCE_RESOURCE_ID",
        "CLAUDE_API_KEY",
        mode="before",
    )
    @classmethod
    def clean_api_keys(cls, v: str) -> str:
        if isinstance(v, str):
            return v.strip().rstrip(",")
        return v

    model_config = {"env_file": ".env", "env_file_encoding": "utf-8"}


settings = Settings()
