"""
app/main.py
FastAPI application entry point.
"""
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.core.config import get_settings
from app.core.database import get_supabase
from app.api.routes import alerts, auth, cameras, health, ingest, zones
from app.websocket import alerts_ws
from app.services.camera_worker import worker_manager
from app.services.analysis_worker import analysis_service_manager

log = logging.getLogger(__name__)
settings = get_settings()


def _check_supabase() -> None:
    """Runs one trivial query at startup so a broken Supabase connection is
    a loud, obvious log line on boot — not something you only discover
    later when a camera/alert write fails (or, before this fix, silently
    vanished)."""
    if settings.database_mode == "memory":
        log.warning("DATABASE_MODE=memory — nothing will persist across restarts. Set it to 'supabase' for real persistence.")
        return
    try:
        get_supabase().table("cameras").select("id").limit(1).execute()
        log.info("Supabase connection OK (database_mode=supabase) — cameras/alerts will persist across restarts.")
    except Exception as exc:
        log.error(
            "Could not reach Supabase at startup (%s). Camera/alert requests will fail with a 503 until this is "
            "fixed. Check SUPABASE_URL / SUPABASE_SERVICE_KEY in your .env and confirm supabase_schema.sql has "
            "been run against that project.",
            exc,
        )


@asynccontextmanager
async def lifespan(_app: FastAPI):
    _check_supabase()
    # The dashboard Analyze page needs a dedicated upload API. Start it with
    # the backend so users no longer need a separate terminal/process.
    analysis_service_manager.start()
    try:
        yield
    finally:
        worker_manager.stop_all()
        analysis_service_manager.stop()

app = FastAPI(
    lifespan=lifespan,
    title=settings.app_name,
    version="0.1.0",
    description="Border Sentinel — backend API",
    docs_url="/docs",
    redoc_url="/redoc",
)

# ── CORS ─────────────────────────────────────────────────────────────────────
# In production, replace the wildcard origin with the real frontend URL.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[origin.strip() for origin in settings.cors_origins.split(",") if origin.strip()],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ── Routers ──────────────────────────────────────────────────────────────────
app.include_router(health.router)
app.include_router(auth.router)
app.include_router(cameras.router)
app.include_router(alerts.router)
app.include_router(ingest.router)
app.include_router(zones.router)
app.include_router(alerts_ws.router)
