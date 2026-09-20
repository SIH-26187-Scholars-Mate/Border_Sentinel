import httpx
import pytest

from ai.utils import backend_client


class _FakeResponse:
    def __init__(self, status_code, json_data):
        self.status_code = status_code
        self._json = json_data
        self.text = str(json_data)

    def json(self):
        return self._json


def test_send_detection_success(monkeypatch):
    captured = {}

    def fake_post(url, json, headers, timeout):
        captured["url"] = url
        captured["json"] = json
        captured["headers"] = headers
        return _FakeResponse(201, {"id": "fake-alert-id", **json})

    monkeypatch.setattr(httpx, "post", fake_post)

    result = backend_client.send_detection(
        camera_id="11111111-1111-1111-1111-111111111111",
        alert_type="intrusion",
        severity="critical",
        confidence=0.95,
    )

    assert result["id"] == "fake-alert-id"
    assert captured["json"]["alert_type"] == "intrusion"  # mapped correctly
    assert "X-Service-Key" in captured["headers"]


def test_send_detection_maps_face_to_valid_backend_enum(monkeypatch):
    captured = {}

    def fake_post(url, json, headers, timeout):
        captured["json"] = json
        return _FakeResponse(201, {"id": "x", **json})

    monkeypatch.setattr(httpx, "post", fake_post)

    backend_client.send_detection(
        camera_id="11111111-1111-1111-1111-111111111111",
        alert_type="face",
        severity="low",
        confidence=0.6,
    )
    # "face" is not a real backend AlertType — must be mapped to one that is.
    assert captured["json"]["alert_type"] == "suspicious_activity"


def test_send_detection_raises_on_non_201(monkeypatch):
    def fake_post(url, json, headers, timeout):
        return _FakeResponse(403, {"detail": "Invalid service key"})

    monkeypatch.setattr(httpx, "post", fake_post)

    with pytest.raises(backend_client.BackendClientError):
        backend_client.send_detection(
            camera_id="11111111-1111-1111-1111-111111111111",
            alert_type="intrusion",
            severity="high",
            confidence=0.8,
        )


def test_send_detection_rejects_unknown_alert_type():
    with pytest.raises(backend_client.BackendClientError):
        backend_client.send_detection(
            camera_id="11111111-1111-1111-1111-111111111111",
            alert_type="not_a_real_type",
            severity="low",
            confidence=0.5,
        )
