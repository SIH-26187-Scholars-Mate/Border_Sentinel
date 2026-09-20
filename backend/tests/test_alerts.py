"""
tests/test_alerts.py
Camera and Alert CRUD endpoint tests.
Cameras are created here too because alerts require a camera_id.
"""
import uuid


# ── Camera CRUD ────────────────────────────────────────────────────────────────

def test_create_camera(client, auth_headers):
    r = client.post(
        "/cameras",
        json={"name": "Gate-1", "location": "North"},
        headers=auth_headers,
    )
    assert r.status_code == 201
    data = r.json()
    assert data["name"] == "Gate-1"
    assert data["is_active"] is True
    assert "id" in data
    assert "created_at" in data


def test_list_cameras_empty(client, auth_headers):
    r = client.get("/cameras", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_list_cameras_returns_created(client, auth_headers, camera):
    r = client.get("/cameras", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()) == 1
    assert r.json()[0]["id"] == camera["id"]


def test_get_camera_not_found(client, auth_headers):
    r = client.get(f"/cameras/{uuid.uuid4()}", headers=auth_headers)
    assert r.status_code == 404


def test_cameras_unauthenticated(client):
    r = client.get("/cameras")
    assert r.status_code == 401


# ── Alert CRUD ─────────────────────────────────────────────────────────────────

def test_create_alert(client, auth_headers, camera):
    r = client.post(
        "/alerts",
        json={
            "camera_id": camera["id"],
            "alert_type": "intrusion",
            "severity": "high",
            "confidence": 0.95,
            "description": "Person crossed fence",
        },
        headers=auth_headers,
    )
    assert r.status_code == 201
    data = r.json()
    assert data["alert_type"] == "intrusion"
    assert data["severity"] == "high"
    assert data["confidence"] == 0.95
    assert data["is_acknowledged"] is False
    assert data["acknowledged_at"] is None


def test_get_alert_by_id(client, auth_headers, camera):
    create = client.post(
        "/alerts",
        json={"camera_id": camera["id"], "alert_type": "intrusion", "severity": "low", "confidence": 0.7},
        headers=auth_headers,
    )
    alert_id = create.json()["id"]

    r = client.get(f"/alerts/{alert_id}", headers=auth_headers)
    assert r.status_code == 200
    assert r.json()["id"] == alert_id


def test_get_alert_not_found(client, auth_headers):
    r = client.get(f"/alerts/{uuid.uuid4()}", headers=auth_headers)
    assert r.status_code == 404


def test_list_alerts_empty(client, auth_headers):
    r = client.get("/alerts", headers=auth_headers)
    assert r.status_code == 200
    assert r.json() == []


def test_list_alerts_with_camera_filter(client, auth_headers, camera):
    # Create two alerts on the same camera
    for _ in range(2):
        client.post(
            "/alerts",
            json={"camera_id": camera["id"], "alert_type": "intrusion", "severity": "low", "confidence": 0.6},
            headers=auth_headers,
        )

    r = client.get(f"/alerts?camera_id={camera['id']}", headers=auth_headers)
    assert r.status_code == 200
    assert len(r.json()) == 2
    # All belong to the same camera
    assert all(a["camera_id"] == camera["id"] for a in r.json())


def test_list_alerts_filter_excludes_other_camera(client, auth_headers, camera):
    """Filter by camera_id must not return alerts from other cameras."""
    # Alert on the fixture camera
    client.post(
        "/alerts",
        json={"camera_id": camera["id"], "alert_type": "intrusion", "severity": "low", "confidence": 0.6},
        headers=auth_headers,
    )
    # Alert on a different (fake) camera id
    other = str(uuid.uuid4())
    client.post(
        "/alerts",
        json={"camera_id": other, "alert_type": "intrusion", "severity": "low", "confidence": 0.6},
        headers=auth_headers,
    )

    r = client.get(f"/alerts?camera_id={camera['id']}", headers=auth_headers)
    assert len(r.json()) == 1


def test_acknowledge_alert(client, auth_headers, camera):
    create = client.post(
        "/alerts",
        json={"camera_id": camera["id"], "alert_type": "intrusion", "severity": "high", "confidence": 0.9},
        headers=auth_headers,
    )
    alert_id = create.json()["id"]

    r = client.patch(f"/alerts/{alert_id}/acknowledge", headers=auth_headers)
    assert r.status_code == 200
    data = r.json()
    assert data["is_acknowledged"] is True
    assert data["acknowledged_at"] is not None


def test_acknowledge_missing_alert(client, auth_headers):
    r = client.patch(f"/alerts/{uuid.uuid4()}/acknowledge", headers=auth_headers)
    assert r.status_code == 404


def test_alerts_unauthenticated(client):
    r = client.get("/alerts")
    assert r.status_code == 401


def test_invalid_alert_type_rejected(client, auth_headers, camera):
    r = client.post(
        "/alerts",
        json={"camera_id": camera["id"], "alert_type": "not-a-real-type", "severity": "low", "confidence": 0.5},
        headers=auth_headers,
    )
    assert r.status_code == 422


def test_confidence_out_of_range_rejected(client, auth_headers, camera):
    r = client.post(
        "/alerts",
        json={"camera_id": camera["id"], "alert_type": "intrusion", "severity": "low", "confidence": 1.5},
        headers=auth_headers,
    )
    assert r.status_code == 422
