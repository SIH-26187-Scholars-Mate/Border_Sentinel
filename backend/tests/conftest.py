"""
tests/conftest.py
Shared fixtures for all test modules.
"""
import os

os.environ["DATABASE_MODE"] = "memory"

import pytest
from starlette.testclient import TestClient

from app.core.config import get_settings
from app.core.security import get_current_user
from app.main import app
from app.schemas.user import UserOut
from app.services import alert_service, camera_service


# ── Store isolation ────────────────────────────────────────────────────────────

@pytest.fixture(autouse=True)
def clear_stores():
    """Wipe both in-memory stores before (and after) every test."""
    camera_service._cameras.clear()
    alert_service._alerts.clear()
    yield
    camera_service._cameras.clear()
    alert_service._alerts.clear()


# ── HTTP client ────────────────────────────────────────────────────────────────

@pytest.fixture
def client() -> TestClient:
    return TestClient(app, raise_server_exceptions=True)


# ── Auth helpers ───────────────────────────────────────────────────────────────

@pytest.fixture
def auth_headers():
    fake_user = UserOut(id="test-uuid-1234", email="dev@test.local", role="authenticated")
    app.dependency_overrides[get_current_user] = lambda: fake_user
    yield {"Authorization": "Bearer fake-token-not-checked"}
    app.dependency_overrides.pop(get_current_user, None)


@pytest.fixture
def svc_headers() -> dict:
    """X-Service-Key header for ingest endpoint."""
    s = get_settings()
    return {"X-Service-Key": s.ai_service_key}


# ── Domain helpers ─────────────────────────────────────────────────────────────

@pytest.fixture
def camera(client: TestClient, auth_headers: dict) -> dict:
    """Create a camera and return its JSON payload."""
    r = client.post(
        "/cameras",
        json={"name": "Test-Cam", "location": "Test Zone", "latitude": 28.0, "longitude": 77.0},
        headers=auth_headers,
    )
    assert r.status_code == 201
    return r.json()
