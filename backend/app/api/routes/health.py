"""
app/api/routes/health.py
Simple liveness probe — GET /health → {"status": "ok"}
"""
from fastapi import APIRouter

router = APIRouter(tags=["health"])


@router.get("/health")
async def health_check() -> dict:
    return {"status": "ok"}
