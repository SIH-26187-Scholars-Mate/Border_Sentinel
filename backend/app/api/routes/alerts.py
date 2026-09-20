"""
app/api/routes/alerts.py
Alert CRUD endpoints — all routes are JWT-protected.

GET    /alerts                        list alerts (optional ?camera_id= filter)
POST   /alerts                        create a manual alert
GET    /alerts/{alert_id}             get a single alert
PATCH  /alerts/{alert_id}/acknowledge mark alert as acknowledged
"""
from typing import Annotated, Optional
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.core.security import get_current_user
from app.schemas.alert import AlertCreate, AlertOut
from app.schemas.user import UserOut
from app.services import alert_service

router = APIRouter(prefix="/alerts", tags=["alerts"])

_Auth = Annotated[UserOut, Depends(get_current_user)]


@router.get("", response_model=list[AlertOut])
async def list_alerts(
    _: _Auth,
    camera_id: Optional[UUID] = Query(default=None, description="Filter by camera UUID"),
    source: Optional[str] = Query(default=None, description="Filter by 'live' or 'video_analysis'"),
) -> list[AlertOut]:
    return alert_service.list_alerts(camera_id=camera_id, source=source)


@router.post("", response_model=AlertOut, status_code=status.HTTP_201_CREATED)
async def create_alert(body: AlertCreate, _: _Auth) -> AlertOut:
    return alert_service.create_alert(body)


@router.get("/{alert_id}", response_model=AlertOut)
async def get_alert(alert_id: UUID, _: _Auth) -> AlertOut:
    alert = alert_service.get_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return alert


@router.patch("/{alert_id}/acknowledge", response_model=AlertOut)
async def acknowledge_alert(alert_id: UUID, _: _Auth) -> AlertOut:
    alert = alert_service.acknowledge_alert(alert_id)
    if not alert:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Alert not found")
    return alert
