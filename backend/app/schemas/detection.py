"""
app/schemas/detection.py
Incoming payload schema from the AI inference microservice.

DetectionIn is what the AI service POSTs to /ingest/detection.
It is intentionally separate from AlertCreate so the two contracts
can evolve independently (e.g. AI may send raw bounding boxes,
frame metadata, model version, etc. that the alert schema doesn't need).
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.alert import AlertSource, AlertType, Severity


class DetectionIn(BaseModel):
    """Detection event emitted by the AI inference pipeline."""

    camera_id: UUID
    alert_type: AlertType
    severity: Severity
    confidence: float = Field(ge=0.0, le=1.0, description="Model confidence 0–1")
    description: Optional[str] = None
    image_url: Optional[str] = None         # Supabase Storage / S3 frame URL
    source: AlertSource = AlertSource.LIVE_CAMERA
    detected_at: Optional[datetime] = None  # AI-side timestamp; falls back to server time
