"""
ai/video/upload_server.py

HTTP API backing the dashboard's "Analyze" page: upload a recorded clip
against a saved camera, get back one plain report of what the AI found in
it — objects, vehicle plates, faces, and (if that camera has a restricted
zone configured) intrusion events.

A camera is REQUIRED (not optional): every intrusion/vehicle/activity event
found is POSTed to the backend as an alert tagged source="video_analysis"
(so the dashboard can tell it apart from a live camera's own alerts), and
an alert has to belong to a real, already-created camera. So the frontend
should not let anyone reach this page until they've created at least one
camera.

This is intentionally simple otherwise: no live MJPEG preview, no shared
preview ports, no dependency on a live camera worker being up. Upload ->
process in a background thread -> poll for the finished report, which is
saved to the dashboard as it's produced. The background thread keeps
running even if the browser navigates away or is closed — /api/video/jobs
and /api/video/jobs/{job_id} let the frontend reconnect to it later.
"""
from __future__ import annotations

import os
import threading
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict

from fastapi import FastAPI, File, Form, HTTPException, UploadFile
from fastapi.middleware.cors import CORSMiddleware

from ai.utils.backend_client import BackendClientError, get_camera_zones, send_detection
from ai.utils.logger import get_logger
from ai.activity.activity_detector import activity_description
from ai.video.report_analyzer import analyze_video_file

log = get_logger(__name__)

UPLOAD_DIR = Path(os.getenv("AI_UPLOAD_DIR", "/tmp/border-sentinel-uploads"))
UPLOAD_DIR.mkdir(parents=True, exist_ok=True)
MAX_UPLOAD_BYTES = int(os.getenv("AI_MAX_UPLOAD_MB", "250")) * 1024 * 1024
ALLOWED_EXTENSIONS = {".mp4", ".mov", ".avi", ".mkv", ".webm", ".m4v"}


def _zone_polygon(camera_id: str):
    """Looks up the camera's saved restricted zone so the report can flag
    intrusions into it. Returns None (intrusion checking simply skipped,
    everything else still runs) if the backend can't be reached or no zone
    has been drawn for that camera yet."""
    try:
        zones = get_camera_zones(camera_id)
    except Exception:
        log.warning("Could not fetch zones for camera %s; skipping intrusion check", camera_id)
        return None
    zone = next((z for z in zones if z.get("enabled", True) and len(z.get("points", [])) >= 3), None)
    if not zone:
        return None
    return [(float(p["x"]), float(p["y"])) for p in zone["points"]]


def _persist_report(camera_id: str, report: dict) -> int:
    """POSTs each event in the report to the backend as an alert tagged
    source='video_analysis', so it shows up in the dashboard's Alerts page
    (filterable separately from live-camera alerts) instead of only living
    inside this one report response. Returns how many were saved; failures
    are logged and skipped rather than failing the whole job — the report
    itself was already computed successfully either way."""
    saved = 0
    # Confidence now comes from the report itself — the real average of that
    # track's/plate's own YOLO detection confidences over the clip — not a
    # fixed placeholder. The 0.75 fallback only fires if a report was built
    # before this field existed, so older jobs don't crash.
    for intrusion in report.get("intrusions", []):
        try:
            send_detection(
                camera_id=camera_id, alert_type="intrusion", severity="critical",
                confidence=intrusion.get("confidence", 0.75),
                description=f"Track {intrusion['track_id']} entered restricted zone at {intrusion['time_seconds']}s (uploaded clip)",
                source="video_analysis",
            )
            saved += 1
        except BackendClientError as exc:
            log.warning("Could not save intrusion alert to backend: %s", exc)

    for vehicle in report.get("vehicles", []):
        try:
            send_detection(
                camera_id=camera_id, alert_type="anpr", severity="high",
                confidence=vehicle.get("confidence", 0.75),
                description=f"Vehicle plate {vehicle['plate']} read at {vehicle['time_seconds']}s (uploaded clip)",
                source="video_analysis",
            )
            saved += 1
        except BackendClientError as exc:
            log.warning("Could not save vehicle alert to backend: %s", exc)

    faces = report.get("face_identities") or {}
    for person in faces.get("watchlist", []):
        try:
            send_detection(
                camera_id=camera_id, alert_type="intrusion", severity="critical",
                confidence=person.get("confidence", 0.75),
                description=f"Watchlist match: face resembles '{person['name']}' at {person['time_seconds']}s — verify manually (uploaded clip)",
                source="video_analysis",
            )
            saved += 1
        except BackendClientError as exc:
            log.warning("Could not save watchlist alert to backend: %s", exc)
    for person in faces.get("unrecognized", []):
        try:
            send_detection(
                camera_id=camera_id, alert_type="intrusion", severity="high",
                confidence=person.get("confidence", 0.75),
                description=f"Unrecognized person (not in authorized list) at {person['time_seconds']}s (uploaded clip)",
                source="video_analysis",
            )
            saved += 1
        except BackendClientError as exc:
            log.warning("Could not save unrecognized-person alert to backend: %s", exc)

    for activity in report.get("activities", []):
        try:
            send_detection(
                camera_id=camera_id, alert_type="activity", severity="medium",
                confidence=activity.get("confidence", 0.75),
                description=f"Track {activity['track_id']} — {activity_description(activity['activity'])} at {activity['time_seconds']}s (uploaded clip)",
                source="video_analysis",
            )
            saved += 1
        except BackendClientError as exc:
            log.warning("Could not save activity alert to backend: %s", exc)

    return saved


class AnalysisService:
    def __init__(self):
        self.lock = threading.Lock()
        self.jobs: Dict[str, dict] = {}
        self.max_jobs = 50

    def start(self, path: Path, job_id: str, camera_id: str):
        with self.lock:
            # Keep completed job history bounded so a long-running service
            # can't grow without limit.
            if len(self.jobs) >= self.max_jobs:
                done = [k for k, v in self.jobs.items() if v["status"] in {"completed", "failed"}]
                for old_id in done[: max(1, len(done) - self.max_jobs + 1)]:
                    self.jobs.pop(old_id, None)
            self.jobs[job_id] = {
                "status": "processing",
                "filename": path.name,
                "camera_id": camera_id,
                "created_at": datetime.now(timezone.utc).isoformat(),
            }

        threading.Thread(target=self._run, args=(path, job_id, camera_id), daemon=True).start()

    def _run(self, path: Path, job_id: str, camera_id: str):
        try:
            fence_polygon = _zone_polygon(camera_id)
            report = analyze_video_file(str(path), fence_polygon=fence_polygon)
            saved = _persist_report(camera_id, report)
            with self.lock:
                created_at = self.jobs.get(job_id, {}).get("created_at")
                self.jobs[job_id] = {
                    "status": "completed", "filename": path.name, "camera_id": camera_id,
                    "created_at": created_at,
                    "report": report, "alerts_saved": saved,
                }
        except Exception as exc:
            log.exception("Video analysis failed for job %s", job_id)
            with self.lock:
                created_at = self.jobs.get(job_id, {}).get("created_at")
                self.jobs[job_id] = {
                    "status": "failed", "filename": path.name, "camera_id": camera_id,
                    "created_at": created_at, "error": str(exc),
                }
        finally:
            try:
                path.unlink(missing_ok=True)
            except OSError:
                pass

    def get(self, job_id: str):
        with self.lock:
            return self.jobs.get(job_id)

    def list_summaries(self):
        """Lightweight history for the Analyze page's "Recent analyses"
        list — just enough to show what was analyzed, on which camera, and
        when. Not the full report (fetch a specific job_id for that).
        Bounded to the same in-memory jobs dict as everything else here, so
        this resets if the AI service restarts and only covers the last
        max_jobs runs."""
        with self.lock:
            items = [
                {
                    "job_id": job_id,
                    "camera_id": job.get("camera_id"),
                    "filename": job.get("filename"),
                    "created_at": job.get("created_at"),
                    "status": job.get("status"),
                }
                for job_id, job in self.jobs.items()
            ]
        items.sort(key=lambda j: j["created_at"] or "", reverse=True)
        return items


def create_upload_app() -> FastAPI:
    app = FastAPI(title="Border Sentinel Video Report")
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=False,
        allow_methods=["*"],
        allow_headers=["*"],
    )
    service = AnalysisService()

    @app.get("/health")
    def health():
        return {"ok": True, "service": "border-sentinel-ai-report"}

    @app.post("/api/video/analyze")
    async def analyze_video(video: UploadFile = File(...), camera_id: str = Form(...)):
        if not camera_id or not camera_id.strip():
            raise HTTPException(status_code=400, detail="camera_id is required — create a camera before analyzing a video.")

        suffix = Path(video.filename or "").suffix.lower()
        if suffix not in ALLOWED_EXTENSIONS:
            raise HTTPException(status_code=400, detail="Unsupported video format. Use MP4, MOV, AVI, MKV, WEBM, or M4V.")

        job_id = str(uuid.uuid4())
        destination = UPLOAD_DIR / f"{job_id}{suffix}"
        total = 0
        try:
            with destination.open("wb") as output:
                while True:
                    chunk = await video.read(1024 * 1024)
                    if not chunk:
                        break
                    total += len(chunk)
                    if total > MAX_UPLOAD_BYTES:
                        raise HTTPException(status_code=413, detail=f"Video is larger than {MAX_UPLOAD_BYTES // (1024 * 1024)} MB.")
                    output.write(chunk)
        except HTTPException:
            destination.unlink(missing_ok=True)
            raise
        except Exception as exc:
            destination.unlink(missing_ok=True)
            raise HTTPException(status_code=500, detail=f"Could not save video: {exc}")

        service.start(destination, job_id, camera_id)
        return {"job_id": job_id, "status": "processing", "filename": video.filename}

    @app.get("/api/video/jobs")
    def list_jobs():
        """History list for the Analyze page — camera, filename, timestamp,
        status for every job this service remembers. Not the full report."""
        return {"jobs": service.list_summaries()}

    @app.get("/api/video/jobs/{job_id}")
    def job_status(job_id: str):
        job = service.get(job_id)
        if not job:
            raise HTTPException(status_code=404, detail="Analysis job not found")
        return {"job_id": job_id, **job}

    return app