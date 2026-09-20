"""
app/schemas/camera.py
API-facing Pydantic schemas for Camera CRUD endpoints.

CameraCreate  → request body for POST /cameras
CameraUpdate  → request body for PATCH /cameras/{id}
CameraOut     → response body (safe, serialisable)
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class CameraCreate(BaseModel):
    name: str
    location: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    stream_url: Optional[str] = None
    is_active: bool = True


class CameraUpdate(BaseModel):
    """All fields optional — PATCH semantics."""

    name: Optional[str] = None
    location: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    stream_url: Optional[str] = None
    is_active: Optional[bool] = None


class CameraOut(BaseModel):
    id: UUID
    camera_number: int  # Stable human-friendly number, e.g. 1 -> CAM-001
    name: str
    location: str
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    stream_url: Optional[str] = None
    is_active: bool
    created_at: datetime
    updated_at: Optional[datetime] = None
    ai_status: str = "stopped"
    ai_running: bool = False
    preview_port: int = 8101
    ai_error: Optional[str] = None
    ai_log_file: Optional[str] = None

    model_config = {"from_attributes": True}
