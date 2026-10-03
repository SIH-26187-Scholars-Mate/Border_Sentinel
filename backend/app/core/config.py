"""
app/core/config.py
Application-wide settings loaded from environment / .env file.
Uses pydantic-settings so every value is type-checked at startup.
"""
from functools import lru_cache
from typing import Literal

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    # ── Application ──────────────────────────────────────────────────────────
    app_name: str = "Border Sentinel"
    app_env: Literal["development", "staging", "production"] = "development"

    # ── Supabase / persistence ───────────────────────────────────────────────
    database_mode: Literal["supabase", "memory"] = "supabase"
    supabase_url: str = ""
    supabase_anon_key: str = ""
    supabase_service_key: str = ""
    ai_service_key: str = ""

    # ── AI Microservice ───────────────────────────────────────────────────────
    backend_url: str = "http://localhost:8000"
    ai_service_url: str = "http://localhost:8001"
    ai_preview_base_port: int = 8100
    ai_upload_api_port: int = 8002
    cors_origins: str = "http://localhost:5173"
    # Optional regex for extra allowed origins, e.g. Vercel preview URLs:
    #   CORS_ORIGIN_REGEX=https://border-sentinel-.*\.vercel\.app
    cors_origin_regex: str = ""

    # ── Deployment ───────────────────────────────────────────────────────────
    # The backend normally spawns the AI module as child processes (webcam
    # workers + the upload-analysis service). A cloud host such as Render has
    # no camera and not enough RAM for torch/YOLO, so set this to false there
    # and run the AI module on your own machine, pointed at the hosted backend.
    enable_ai_workers: bool = True

    # ── Security ─────────────────────────────────────────────────────────────
    supabase_jwks_url: str = ""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    """Return cached Settings instance (parsed once at first call)."""
    return Settings()
