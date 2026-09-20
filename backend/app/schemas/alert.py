"""
app/schemas/alert.py
API-facing Pydantic schemas for Alert CRUD endpoints.

AlertCreate   → request body for POST /alerts (manual alert creation)
AlertOut      → response body (safe, serialisable)

AlertType and Severity enums are imported from app.models.alert so there
is a single source of truth for the allowed values.
"""
from datetime import datetime
from typing import Optional
from uuid import UUID

from pydantic import BaseModel, Field

from app.models.alert import AlertSource, AlertType, Severity


class AlertCreate(BaseModel):
    camera_id: UUID
    alert_type: AlertType
    severity: Severity
    confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    description: Optional[str] = None
    image_url: Optional[str] = None
    source: AlertSource = AlertSource.LIVE_CAMERA


class AlertOut(BaseModel):
    id: UUID
    camera_id: UUID
    alert_type: AlertType
    severity: Severity
    confidence: float
    description: Optional[str] = None
    image_url: Optional[str] = None
    source: AlertSource = AlertSource.LIVE_CAMERA
    is_acknowledged: bool
    created_at: datetime
    acknowledged_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
