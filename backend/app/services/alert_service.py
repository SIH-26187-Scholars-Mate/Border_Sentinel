"""Alert persistence and CRUD operations."""
import uuid
from datetime import datetime, timezone
from typing import Optional

from fastapi import HTTPException, status
from uuid import UUID

from app.core.config import get_settings
from app.core.database import get_supabase
from app.schemas.alert import AlertCreate, AlertOut

_alerts: dict[str, dict] = {}


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _memory() -> bool:
    return get_settings().database_mode == "memory"


def create_alert(data: AlertCreate, created_at: Optional[datetime] = None) -> AlertOut:
    timestamp = created_at or _now()
    if _memory():
        record = {"id": uuid.uuid4(), "is_acknowledged": False, "acknowledged_at": None,
                  "created_at": timestamp, **data.model_dump()}
        _alerts[str(record["id"])] = record
        return AlertOut(**record)

    payload = {"id": str(uuid.uuid4()), "is_acknowledged": False, "acknowledged_at": None,
               "created_at": timestamp.isoformat(), **data.model_dump(mode="json")}
    try:
        rows = get_supabase().table("alerts").insert(payload).execute().data
    except Exception as exc:
        # Never silently fall back to RAM in production: doing so makes an
        # apparently successful detection disappear when the backend restarts.
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Alert could not be persisted to Supabase: {exc}",
        ) from exc
    if not rows:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail="Supabase accepted the request but returned no saved alert row.",
        )
    return AlertOut(**rows[0])

def list_alerts(camera_id: Optional[UUID] = None, source: Optional[str] = None) -> list[AlertOut]:
    if _memory():
        rows = list(_alerts.values())
        if camera_id is not None:
            rows = [r for r in rows if str(r["camera_id"]) == str(camera_id)]
        if source is not None:
            rows = [r for r in rows if r.get("source", "live") == source]
        rows.sort(key=lambda r: r["created_at"], reverse=True)
        return [AlertOut(**r) for r in rows]

    try:
        query = get_supabase().table("alerts").select("*").order("created_at", desc=True)
        if camera_id is not None:
            query = query.eq("camera_id", str(camera_id))
        if source is not None:
            query = query.eq("source", source)
        rows = query.execute().data
        return [AlertOut(**r) for r in rows]
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not load alert history from Supabase: {exc}",
        ) from exc


def get_alert(alert_id: UUID) -> Optional[AlertOut]:
    if _memory():
        record = _alerts.get(str(alert_id))
        return AlertOut(**record) if record else None

    try:
        rows = get_supabase().table("alerts").select("*").eq("id", str(alert_id)).limit(1).execute().data
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not load alert from Supabase: {exc}",
        ) from exc
    return AlertOut(**rows[0]) if rows else None


def acknowledge_alert(alert_id: UUID) -> Optional[AlertOut]:
    acknowledged_at = _now()
    if _memory():
        record = _alerts.get(str(alert_id))
        if not record:
            return None
        record.update({"is_acknowledged": True, "acknowledged_at": acknowledged_at})
        return AlertOut(**record)

    try:
        rows = (get_supabase().table("alerts")
                .update({"is_acknowledged": True, "acknowledged_at": acknowledged_at.isoformat()})
                .eq("id", str(alert_id)).select("*").execute().data)
    except Exception as exc:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=f"Could not update alert in Supabase: {exc}",
        ) from exc
    return AlertOut(**rows[0]) if rows else None