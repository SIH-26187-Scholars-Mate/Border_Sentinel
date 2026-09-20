"""
tests/test_camera_persistence.py

Regression test for the "cameras vanish on restart" bug: camera_service
used to silently swallow every Supabase failure and fall back to an
in-memory dict, so a camera could look saved and then disappear the next
time the process restarted. It should now raise a clear 503 instead,
matching how alert_service already treats a broken Supabase connection.
"""
import pytest
from fastapi import HTTPException

from app.schemas.camera import CameraCreate
from app.services import camera_service


def _break_supabase(monkeypatch):
    """Force the Supabase code path (as if DATABASE_MODE=supabase) and make
    get_supabase() raise, simulating a bad connection/credentials."""
    monkeypatch.setattr(camera_service, "_memory", lambda: False)

    def _raise():
        raise RuntimeError("could not connect to Supabase")

    monkeypatch.setattr(camera_service, "get_supabase", _raise)


def test_create_camera_raises_instead_of_falling_back_to_memory(monkeypatch):
    _break_supabase(monkeypatch)
    with pytest.raises(HTTPException) as exc_info:
        camera_service.create_camera(CameraCreate(name="Gate-1", location="North"))
    assert exc_info.value.status_code == 503
    # The camera must NOT have been silently written to the in-memory store.
    assert camera_service._cameras == {}


def test_list_cameras_raises_instead_of_returning_stale_memory(monkeypatch):
    _break_supabase(monkeypatch)
    with pytest.raises(HTTPException) as exc_info:
        camera_service.list_cameras()
    assert exc_info.value.status_code == 503
