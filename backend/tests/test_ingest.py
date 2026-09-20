"""
tests/test_ingest.py
AI ingest endpoint tests — /ingest/detection.

WebSocket broadcast is not tested here (covered by the Phase 6 checkpoint
script).  During these tests no WS clients are connected, so broadcast()
is a safe no-op.
"""
import uuid

CAM_ID = "00000000-0000-0000-0000-000000000001"

VALID_DETECTION = {
    "camera_id": CAM_ID,
    "alert_type": "suspicious_activity",
    "severity": "critical",
    "confidence": 0.97,
    "description": "Unit test detection",
    "image_url": "https://storage.example.com/test/frame.jpg",
}


# ── Authentication / authorisation ────────────────────────────────────────────

def test_ingest_no_key_is_422(client):
    """Missing X-Service-Key header → 422 (required header)."""
    r = client.post("/ingest/detection", json=VALID_DETECTION)
    assert r.status_code == 422


def test_ingest_wrong_key_is_403(client):
    r = client.post(
        "/ingest/detection",
        json=VALID_DETECTION,
        headers={"X-Service-Key": "definitely-wrong"},
    )
    assert r.status_code == 403
    assert "service key" in r.json()["detail"].lower()


# ── Happy path ────────────────────────────────────────────────────────────────

def test_ingest_creates_alert(client, svc_headers):
    r = client.post("/ingest/detection", json=VALID_DETECTION, headers=svc_headers)
    assert r.status_code == 201
    data = r.json()
    assert data["alert_type"] == "suspicious_activity"
    assert data["severity"] == "critical"
    assert data["confidence"] == 0.97
    assert data["is_acknowledged"] is False
    assert "id" in data


def test_ingest_alert_appears_in_get(client, svc_headers, auth_headers):
    """Alert created via ingest must be retrievable via GET /alerts."""
    r = client.post("/ingest/detection", json=VALID_DETECTION, headers=svc_headers)
    assert r.status_code == 201
    alert_id = r.json()["id"]

    r = client.get("/alerts", headers=auth_headers)
    assert r.status_code == 200
    ids = [a["id"] for a in r.json()]
    assert alert_id in ids


def test_ingest_image_url_preserved(client, svc_headers):
    r = client.post("/ingest/detection", json=VALID_DETECTION, headers=svc_headers)
    assert r.json()["image_url"] == VALID_DETECTION["image_url"]


def test_ingest_description_preserved(client, svc_headers):
    r = client.post("/ingest/detection", json=VALID_DETECTION, headers=svc_headers)
    assert r.json()["description"] == VALID_DETECTION["description"]


# ── Schema validation ─────────────────────────────────────────────────────────

def test_ingest_invalid_alert_type_rejected(client, svc_headers):
    bad = {**VALID_DETECTION, "alert_type": "flying-saucer"}
    r = client.post("/ingest/detection", json=bad, headers=svc_headers)
    assert r.status_code == 422


def test_ingest_confidence_above_1_rejected(client, svc_headers):
    bad = {**VALID_DETECTION, "confidence": 1.1}
    r = client.post("/ingest/detection", json=bad, headers=svc_headers)
    assert r.status_code == 422


def test_ingest_confidence_below_0_rejected(client, svc_headers):
    bad = {**VALID_DETECTION, "confidence": -0.1}
    r = client.post("/ingest/detection", json=bad, headers=svc_headers)
    assert r.status_code == 422


def test_ingest_multiple_detections_all_stored(client, svc_headers, auth_headers):
    """Three rapid-fire detections must all appear in GET /alerts."""
    ids = set()
    for i in range(3):
        r = client.post(
            "/ingest/detection",
            json={**VALID_DETECTION, "confidence": round(0.8 + i * 0.05, 2)},
            headers=svc_headers,
        )
        assert r.status_code == 201
        ids.add(r.json()["id"])

    r = client.get("/alerts", headers=auth_headers)
    stored_ids = {a["id"] for a in r.json()}
    assert ids.issubset(stored_ids)


# ── source field (live vs video_analysis) ─────────────────────────────────────

def test_ingest_defaults_source_to_live(client, svc_headers):
    r = client.post("/ingest/detection", json=VALID_DETECTION, headers=svc_headers)
    assert r.status_code == 201
    assert r.json()["source"] == "live"


def test_ingest_accepts_video_analysis_source(client, svc_headers):
    body = {**VALID_DETECTION, "source": "video_analysis"}
    r = client.post("/ingest/detection", json=body, headers=svc_headers)
    assert r.status_code == 201
    assert r.json()["source"] == "video_analysis"


def test_alerts_can_be_filtered_by_source(client, auth_headers, svc_headers):
    client.post("/ingest/detection", json=VALID_DETECTION, headers=svc_headers)
    client.post("/ingest/detection", json={**VALID_DETECTION, "source": "video_analysis"}, headers=svc_headers)

    live_only = client.get("/alerts?source=live", headers=auth_headers).json()
    upload_only = client.get("/alerts?source=video_analysis", headers=auth_headers).json()

    assert all(a["source"] == "live" for a in live_only)
    assert all(a["source"] == "video_analysis" for a in upload_only)
    assert len(live_only) == 1
    assert len(upload_only) == 1
