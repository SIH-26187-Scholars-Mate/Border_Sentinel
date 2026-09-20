"""
app/api/routes/ingest.py
AI detection ingest endpoint — secured by static service key, NOT user JWT.

The AI microservice authenticates by sending its shared secret in the
X-Service-Key header (verified by verify_service_key from core/security.py).
No user token is involved; this endpoint is machine-to-machine only.

Flow:
  DetectionIn  →  AlertCreate  →  alert_service.create_alert()
                                       ↓
                               (Phase 6: ws_manager.broadcast)
"""
from fastapi import APIRouter, Depends, status
from uuid import UUID

from app.core.security import verify_service_key
from app.schemas.alert import AlertCreate, AlertOut
from app.schemas.detection import DetectionIn
from app.services import alert_service
from app.websocket.manager import ws_manager
from app.services.zone_service import list_zones

router = APIRouter(prefix="/ingest", tags=["ingest"])


@router.post(
    "/detection",
    response_model=AlertOut,
    status_code=status.HTTP_201_CREATED,
    dependencies=[Depends(verify_service_key)],
    summary="Ingest an AI detection event",
    description=(
        "Called by the AI microservice. Requires X-Service-Key header. "
        "Converts the detection payload into a persisted Alert and (Phase 6) "
        "broadcasts it over the WebSocket channel."
    ),
)
async def ingest_detection(body: DetectionIn) -> AlertOut:
    # Map AI payload → alert creation schema
    alert_data = AlertCreate(
        camera_id=body.camera_id,
        alert_type=body.alert_type,
        severity=body.severity,
        confidence=body.confidence,
        description=body.description,
        image_url=body.image_url,
        source=body.source,
    )

    alert = alert_service.create_alert(alert_data)

    # Broadcast to all live WebSocket clients
    await ws_manager.broadcast(alert.model_dump_json())

    return alert

@router.get('/zones/{camera_id}', dependencies=[Depends(verify_service_key)])
async def ingest_zones(camera_id: UUID):
    return [z.model_dump(mode='json') for z in list_zones(camera_id)]
