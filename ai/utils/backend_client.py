"""
ai/utils/backend_client.py
Sends detection events into the backend's POST /ingest/detection endpoint.

IMPORTANT — alert_type must be one of the values backend actually defines
in app/models/alert.py (AlertType enum). As of the current backend, that is:
    intrusion, unauthorized_vehicle, suspicious_activity,
    perimeter_breach, unattended_object, other
There is NO "face" / "anpr" / "activity" / "detection" alert type — every
detector in this module maps its finding onto one of the six values above.
If backend adds a dedicated FACE_DETECTED or ANPR_MATCH type later, update
ALERT_TYPE_MAP below to match — don't invent a string backend doesn't know.
"""
from datetime import datetime, timezone
from typing import Optional

import httpx

from ai.utils.config import get_settings
from ai.utils.logger import get_logger

log = get_logger(__name__)

# Maps this module's internal concept of "what kind of detector fired" onto
# backend's real AlertType enum values.
ALERT_TYPE_MAP = {
    "intrusion": "intrusion",
    "face": "suspicious_activity",
    "anpr": "unauthorized_vehicle",
    "activity": "suspicious_activity",
    "unattended_object": "unattended_object",
    "other": "other",
}


class BackendClientError(Exception):
    """Raised when the backend rejects or is unreachable for a detection POST."""


def send_detection(
    camera_id: str,
    alert_type: str,
    severity: str,
    confidence: float,
    description: Optional[str] = None,
    image_url: Optional[str] = None,
    source: str = "live",
    timeout: float = 5.0,
) -> dict:
    """
    POST a detection to backend's /ingest/detection.

    alert_type: a key from ALERT_TYPE_MAP above (e.g. "intrusion", "face"),
                NOT a raw backend enum value — this function does the mapping.
    severity:   one of "low", "medium", "high", "critical" (matches backend
                exactly, no mapping needed).
    confidence: 0.0-1.0.
    source:     "live" (default, a currently-running camera worker) or
                "video_analysis" (the uploaded-video Analyze report) — lets
                the dashboard tell the two apart.

    Raises BackendClientError on any non-2xx response or connection failure
    so callers can decide whether to retry, log, or drop the detection.
    """
    settings = get_settings()

    if alert_type not in ALERT_TYPE_MAP:
        raise BackendClientError(
            f"Unknown alert_type '{alert_type}' — must be one of {list(ALERT_TYPE_MAP)}"
        )

    payload = {
        "camera_id": str(camera_id),
        "alert_type": ALERT_TYPE_MAP[alert_type],
        "severity": severity,
        "confidence": round(float(confidence), 4),
        "description": description,
        "image_url": image_url,
        "source": source,
        "detected_at": datetime.now(timezone.utc).isoformat(),
    }

    url = f"{settings.backend_url.rstrip('/')}/ingest/detection"
    headers = {"X-Service-Key": settings.service_key}

    try:
        resp = httpx.post(url, json=payload, headers=headers, timeout=timeout)
    except httpx.RequestError as exc:
        log.error("Could not reach backend at %s: %s", url, exc)
        raise BackendClientError(f"Could not reach backend at {url}: {exc}") from exc

    if resp.status_code != 201:
        log.error("Backend rejected detection (%s): %s", resp.status_code, resp.text)
        raise BackendClientError(f"Backend returned {resp.status_code}: {resp.text}")

    log.info("Detection sent: %s (severity=%s, confidence=%.2f)", alert_type, severity, confidence)
    return resp.json()


def get_camera_zones(camera_id: str):
    settings=get_settings(); url=f"{settings.backend_url.rstrip('/')}/ingest/zones/{camera_id}"
    try:
        resp=httpx.get(url,headers={'X-Service-Key':settings.service_key},timeout=3.0)
        if resp.status_code != 200: return []
        return resp.json()
    except httpx.RequestError:
        return []
