"""
app/models/alert.py
Domain model representing a row in the `alerts` Supabase table.
Includes the AlertType and Severity enums used across the codebase.
"""
from datetime import datetime
from enum import StrEnum
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field


class AlertType(StrEnum):
    INTRUSION = "intrusion"
    UNAUTHORIZED_VEHICLE = "unauthorized_vehicle"
    SUSPICIOUS_ACTIVITY = "suspicious_activity"
    PERIMETER_BREACH = "perimeter_breach"
    UNATTENDED_OBJECT = "unattended_object"
    OTHER = "other"


class AlertSource(StrEnum):
    """Where a detection came from — lets the dashboard tell events raised
    by a live, currently-running camera apart from ones found by analyzing
    an uploaded recording after the fact."""

    LIVE_CAMERA = "live"
    VIDEO_ANALYSIS = "video_analysis"


class Severity(StrEnum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    CRITICAL = "critical"


class Alert(BaseModel):
    """Mirrors the `alerts` DB table exactly."""

    id: UUID
    camera_id: UUID
    alert_type: AlertType
    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0)  # AI model confidence 0–1
    description: Optional[str] = None
    image_url: Optional[str] = None             # S3 / Supabase Storage URL
    source: AlertSource = AlertSource.LIVE_CAMERA
    is_acknowledged: bool = False
    created_at: datetime
    acknowledged_at: Optional[datetime] = None
