"""
app/models/camera.py
Domain model representing a row in the `cameras` Supabase table.
This is the internal data layer shape — API-facing shapes live in schemas/.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel


class Camera(BaseModel):
    """Mirrors the `cameras` DB table exactly."""

    id: UUID
    camera_number: int
    name: str
    location: str                       # Human-readable location label
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    stream_url: Optional[str] = None    # RTSP / HTTP stream URI
    is_active: bool = True
    created_at: datetime
    updated_at: Optional[datetime] = None
