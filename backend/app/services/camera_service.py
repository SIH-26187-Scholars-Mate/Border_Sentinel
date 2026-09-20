"""Camera persistence and CRUD operations."""
import uuid
from datetime import datetime, timezone
from typing import Optional
from uuid import UUID

from fastapi import HTTPException, status

from app.core.config import get_settings
from app.core.database import get_supabase
from app.schemas.camera import CameraCreate, CameraOut, CameraUpdate
from app.services.camera_worker import worker_manager

_cameras: dict[str, dict] = {}


def _now() -> datetime:
    return datetime.now(tz=timezone.utc)


def _memory() -> bool:
    return get_settings().database_mode == "memory"


def _unavailable(action: str, exc: Exception) -> HTTPException:
    # NEVER silently fall back to RAM in production (DATABASE_MODE=supabase):
    # doing so is exactly why a camera can look saved and then vanish the
    # next time the backend restarts — the "successful" save only ever
    # existed in this process's memory. Raise instead, matching how
    # alert_service already treats a broken Supabase connection.
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail=f"Camera could not be {action} in Supabase: {exc}",
    )


def _with_runtime(record: dict) -> CameraOut:
    number = int(record["camera_number"])
    runtime = worker_manager.status(record["id"], number)
    return CameraOut(**record, **runtime)


def _start_if_active(record: dict) -> None:
    if record.get("is_active", True):
        worker_manager.start(record["id"], int(record["camera_number"]), record.get("stream_url"))


def create_camera(data: CameraCreate) -> CameraOut:
    if _memory():
        next_number = max((r.get("camera_number", 0) for r in _cameras.values()), default=0) + 1
        record = {"id": uuid.uuid4(), "camera_number": next_number, "created_at": _now(), "updated_at": None, **data.model_dump()}
        _cameras[str(record["id"])] = record
        _start_if_active(record)
        return _with_runtime(record)

    payload = {"id": str(uuid.uuid4()), **data.model_dump()}
    try:
        rows = get_supabase().table("cameras").insert(payload).execute().data
    except Exception as exc:
        raise _unavailable("saved", exc) from exc
    if not rows:
        raise HTTPException(status_code=status.HTTP_503_SERVICE_UNAVAILABLE, detail="Supabase accepted the request but returned no saved camera row.")
    record = rows[0]
    _start_if_active(record)
    return _with_runtime(record)


def list_cameras() -> list[CameraOut]:
    if _memory():
        return [_with_runtime(r) for r in _cameras.values()]

    try:
        rows = get_supabase().table("cameras").select("*").order("created_at", desc=False).execute().data
    except Exception as exc:
        raise _unavailable("listed", exc) from exc
    return [_with_runtime(r) for r in rows]


def get_camera(camera_id: UUID) -> Optional[CameraOut]:
    record = _raw_camera(camera_id)
    return _with_runtime(record) if record else None


def _raw_camera(camera_id: UUID) -> Optional[dict]:
    if _memory():
        return _cameras.get(str(camera_id))

    try:
        rows = get_supabase().table("cameras").select("*").eq("id", str(camera_id)).limit(1).execute().data
    except Exception as exc:
        raise _unavailable("read", exc) from exc
    return rows[0] if rows else None


def update_camera(camera_id: UUID, data: CameraUpdate) -> Optional[CameraOut]:
    updates = data.model_dump(exclude_none=True)
    record = _raw_camera(camera_id)
    if not record:
        return None
    source_changed = any(k in updates for k in ("stream_url", "is_active"))

    if _memory():
        record.update({**updates, "updated_at": _now()})
    elif updates:
        try:
            rows = (get_supabase().table("cameras").update(updates)
                    .eq("id", str(camera_id)).select("*").execute().data)
        except Exception as exc:
            raise _unavailable("updated", exc) from exc
        if rows:
            record = rows[0]

    if source_changed:
        if record.get("is_active", True):
            worker_manager.restart(record["id"], int(record["camera_number"]), record.get("stream_url"))
        else:
            worker_manager.stop(record["id"])
    return _with_runtime(record)


def delete_camera(camera_id: UUID) -> bool:
    worker_manager.stop(camera_id)
    if _memory():
        return _cameras.pop(str(camera_id), None) is not None

    try:
        result = get_supabase().table("cameras").delete().eq("id", str(camera_id)).execute()
    except Exception as exc:
        raise _unavailable("deleted", exc) from exc
    return bool(result.data)


def start_camera(camera_id: UUID) -> Optional[CameraOut]:
    record = _raw_camera(camera_id)
    if not record:
        return None
    if _memory():
        record["is_active"] = True
    else:
        try:
            rows = get_supabase().table("cameras").update({"is_active": True}).eq("id", str(camera_id)).select("*").execute().data
        except Exception as exc:
            raise _unavailable("started", exc) from exc
        if rows:
            record = rows[0]
    worker_manager.start(record["id"], int(record["camera_number"]), record.get("stream_url"))
    return _with_runtime(record)


def stop_camera(camera_id: UUID) -> Optional[CameraOut]:
    record = _raw_camera(camera_id)
    if not record:
        return None
    worker_manager.stop(camera_id)
    if _memory():
        record["is_active"] = False
    else:
        try:
            rows = get_supabase().table("cameras").update({"is_active": False}).eq("id", str(camera_id)).select("*").execute().data
        except Exception as exc:
            raise _unavailable("stopped", exc) from exc
        if rows:
            record = rows[0]
    return _with_runtime(record)


def worker_status(camera_id: UUID) -> Optional[dict]:
    record = _raw_camera(camera_id)
    if not record:
        return None
    return worker_manager.status(record["id"], int(record["camera_number"]))


def stop_all_cameras() -> int:
    """Stop every running AI worker and mark persisted cameras inactive.

    This is used at explicit application logout so a local webcam/RTSP
    process cannot continue running after the authenticated session ends.
    """
    worker_manager.stop_all()

    if _memory():
        stopped = 0
        for record in _cameras.values():
            if record.get("is_active", True):
                record["is_active"] = False
                record["updated_at"] = _now()
                stopped += 1
        return stopped

    try:
        rows = (get_supabase().table("cameras").update({"is_active": False})
                .eq("is_active", True).select("id").execute().data)
    except Exception as exc:
        raise _unavailable("stopped", exc) from exc
    return len(rows or [])