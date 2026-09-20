"""
ai/pipeline.py
Wires video input -> detection -> tracking -> intrusion/activity/ANPR
checks -> backend alerts into one loop. This is what main.py runs.

A camera_id must be supplied — it should match a real camera row already
created in the backend (via POST /cameras), since backend's ingest route
expects a valid camera_id.
"""
import json
import os
import time
from typing import Dict, List, Optional, Tuple
from urllib.parse import urlsplit
from uuid import uuid4

import cv2
import numpy as np

from ai.activity.activity_detector import ActivityDetector
from ai.anpr.anpr_processor import ANPRProcessor
from ai.detection.detector import Detection, Detector
from ai.face.face_detector import FaceDetector
from ai.intrusion.virtual_fence import VirtualFence, polygon_for_frame
from ai.tracking.tracker import CentroidTracker
from ai.utils.backend_client import BackendClientError, send_detection, get_camera_zones
from ai.utils.config import get_settings
from ai.utils.logger import get_logger
from ai.video.frame_processor import FrameProcessor
from ai.video.video_stream import VideoStream

log = get_logger(__name__)

# YOLOv8's default COCO weights use these class names for anything with
# wheels — this is what "vehicle detected" means for ANPR purposes.
VEHICLE_CLASSES = {"car", "truck", "bus", "motorcycle"}

# How many frames a track must go unseen before we're willing to fire a
# fresh ANPR alert for the "same" track ID again (e.g. it re-enters frame).
ANPR_COOLDOWN_FRAMES = 60

# Set BS_PROFILE=1 to log the average time each stage takes per frame
# (every 100 frames), so you can see what is actually limiting FPS.
_PROFILE = os.getenv("BS_PROFILE") == "1"


def _severity_for(activity: str) -> str:
    return {
        "rapid_movement": "medium",
        "wrong_direction": "high",
        "loitering": "low",
        "vehicle_loitering": "high",
    }.get(activity, "low")


class Pipeline:
    def __init__(
        self,
        camera_id: str,
        run_face: bool = True,
        run_activity: bool = True,
        run_anpr: bool = True,
        # Run the (CPU-heavy) Haar face cascades only on every Nth frame and
        # reuse the last result in between. Faces don't move far in 2-3
        # frames, and this stage otherwise dominates per-frame time.
        face_every_n: int = 3,
        # Dependency injection hooks — real objects are constructed by
        # default (and Detector() requires torch/ultralytics to be
        # installed), but tests can pass in fakes here to exercise the
        # pipeline's wiring logic without needing a real model loaded.
        detector: Optional[Detector] = None,
        tracker: Optional[CentroidTracker] = None,
        face_detector: Optional[FaceDetector] = None,
        activity_detector: Optional[ActivityDetector] = None,
        anpr_processor: Optional[ANPRProcessor] = None,
        frame_callback=None,
        evidence_callback=None,
        preview_port: Optional[int] = None,
        public_host: Optional[str] = None,
    ):
        settings = get_settings()
        self._camera_id = camera_id
        self._frame_callback = frame_callback
        # evidence_callback(frame, job_id) -> None: hands a raw frame off to
        # whatever is running the per-camera preview server, so it can be
        # fetched later at /snapshot.jpg?job=<job_id>. preview_port/public_host
        # let us build that URL ourselves so it lands on the alert as
        # image_url. All optional — with none of these set (e.g. existing
        # tests, or --no-preview), alerts simply keep image_url=None exactly
        # as before.
        self._evidence_callback = evidence_callback
        self._preview_port = preview_port
        self._public_host = public_host or urlsplit(settings.backend_url).hostname or "localhost"
        self._detector = detector if detector is not None else Detector()
        self._tracker = tracker if tracker is not None else CentroidTracker()
        self._face_detector = (face_detector if face_detector is not None else FaceDetector()) if run_face else None
        self._activity_detector = (
            activity_detector if activity_detector is not None else ActivityDetector()
        ) if run_activity else None
        self._anpr = (anpr_processor if anpr_processor is not None else ANPRProcessor()) if run_anpr else None

        self._fence: Optional[VirtualFence] = None
        if settings.fence_zone:
            polygon = json.loads(settings.fence_zone)
            self._fence = VirtualFence(polygon)
            log.info("Virtual fence active with %d points", len(polygon))

        # track_id -> last frame index an ANPR alert was fired for it
        self._anpr_last_emitted: Dict[int, int] = {}
        # track_id -> that track's own detection confidence history, so
        # intrusion/activity alerts can report a real average instead of a
        # fixed placeholder number.
        self._track_confidences: Dict[int, List[float]] = {}
        self._stage_ms: Dict[str, float] = {}
        self._face_every_n = max(1, int(face_every_n))
        self._last_faces: list = []
        self._frame_index = 0
        self._last_zone_refresh = -9999
        self._fps_started = time.perf_counter()
        self._fps_frames = 0
        self._fps = 0.0
        # Aggregated object counts for recorded-video history. These are
        # persisted once per analysis job instead of creating one DB row per frame.
        self._class_counts: Dict[str, int] = {}
        self._event_counts: Dict[str, int] = {}

    def _refresh_zones(self, frame_shape=None):
        zones = get_camera_zones(self._camera_id)
        self._last_zone_refresh = self._frame_index
        if zones:
            zone = next((z for z in zones if z.get("enabled", True) and len(z.get("points", [])) >= 3), None)
            if zone:
                raw_points = [(float(p["x"]), float(p["y"])) for p in zone["points"]]
                if frame_shape is not None:
                    frame_height, frame_width = frame_shape[:2]
                    points = polygon_for_frame(raw_points, frame_width, frame_height)
                else:
                    # If the frame size is not known yet, retain the stored
                    # coordinates. The first frame refresh below will remap
                    # them to the actual camera dimensions.
                    points = raw_points
                self._fence = VirtualFence(points)
                return
        # Keep env-configured fence if backend has no saved zone.

    def _report(self, alert_type: str, severity: str, confidence: float, description: str, frame=None):
        image_url = self._capture_evidence(frame) if frame is not None else None
        try:
            send_detection(
                camera_id=self._camera_id,
                alert_type=alert_type,
                severity=severity,
                confidence=confidence,
                description=description,
                image_url=image_url,
            )
        except BackendClientError as exc:
            # Don't crash the whole pipeline because the backend hiccupped
            # once — log it and keep processing frames.
            log.warning("Failed to report %s: %s", alert_type, exc)

    def _capture_evidence(self, frame) -> Optional[str]:
        """Hand this frame to the preview server under a one-off job id and
        return the URL the frontend can load it from — or None if no preview
        server is wired up (--no-preview, or a test with no evidence_callback)."""
        if self._evidence_callback is None or self._preview_port is None:
            return None
        job_id = f"evidence-{uuid4().hex[:12]}"
        try:
            self._evidence_callback(frame, job_id)
        except Exception as exc:
            log.warning("Failed to capture evidence frame: %s", exc)
            return None
        return f"http://{self._public_host}:{self._preview_port}/snapshot.jpg?job={job_id}"

    def _anpr_can_emit(self, track_id: int) -> bool:
        last = self._anpr_last_emitted.get(track_id)
        return last is None or (self._frame_index - last) > ANPR_COOLDOWN_FRAMES

    def _draw_overlay(self, frame, detections, faces, events):
        """Draw AI results onto the frame that is sent to the browser preview."""
        for detection in detections:
            x1, y1, x2, y2 = map(int, detection.bbox)
            label = f"{detection.class_name} {detection.confidence:.0%}"
            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 255, 0), 2)
            (tw, th), _ = cv2.getTextSize(label, cv2.FONT_HERSHEY_SIMPLEX, 0.55, 2)
            cv2.rectangle(frame, (x1, max(0, y1 - th - 8)), (x1 + tw + 8, y1), (0, 255, 0), -1)
            cv2.putText(frame, label, (x1 + 4, max(th + 2, y1 - 5)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (0, 0, 0), 2, cv2.LINE_AA)

        for tid, bbox in getattr(self, "_current_tracked", {}).items():
            x1,y1,x2,y2=map(int,bbox)
            cv2.putText(frame, f"ID {tid}", (x1, min(frame.shape[0]-8, y2+18)), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (255,255,255), 2, cv2.LINE_AA)

        if self._fence is not None:
            pts = np.array(self._fence._polygon, dtype=np.int32)
            cv2.polylines(frame, [pts], True, (255, 80, 80), 2)

        for x, y, w, h in faces:
            cv2.rectangle(frame, (x, y), (x + w, y + h), (255, 200, 0), 2)
            cv2.putText(frame, "FACE", (x, max(20, y - 6)),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.55, (255, 200, 0), 2, cv2.LINE_AA)

        # Show the most useful AI events in a compact banner.
        event_text = [f"FPS {self._fps:.1f}"]
        for event in events:
            if event.get("type") == "anpr" and event.get("plate"):
                event_text.append(f"PLATE: {event['plate']}")
            elif event.get("type") == "intrusion":
                event_text.append("INTRUSION")
            elif event.get("type") == "activity":
                event_text.append(str(event.get("activity", "ACTIVITY")).upper())
        banner = "  |  ".join(event_text)
        if banner:
            cv2.rectangle(frame, (0, 0), (frame.shape[1], 38), (20, 20, 20), -1)
            cv2.putText(frame, banner[:120], (12, 26), cv2.FONT_HERSHEY_SIMPLEX,
                        0.65, (255, 255, 255), 2, cv2.LINE_AA)

    def _lap(self, stage: str, t0: float) -> float:
        """Add the time since t0 to `stage` and return a fresh timestamp."""
        now = time.perf_counter()
        if _PROFILE:
            self._stage_ms[stage] = self._stage_ms.get(stage, 0.0) + (now - t0) * 1000
        return now

    def _log_profile(self):
        if not _PROFILE or self._frame_index % 100 != 0:
            return
        parts = ", ".join(f"{k}={v / 100:.0f}ms" for k, v in self._stage_ms.items())
        log.info("Avg per frame over last 100: %s (measured fps=%.1f)", parts, self._fps)
        self._stage_ms.clear()

    def process_frame(self, frame) -> dict:
        """Run AI and return a summary. The frame is annotated for the live preview."""
        self._frame_index += 1
        self._fps_frames += 1
        elapsed=time.perf_counter()-self._fps_started
        if elapsed >= 1.0:
            self._fps=self._fps_frames/elapsed; self._fps_frames=0; self._fps_started=time.perf_counter()

        if self._frame_index - self._last_zone_refresh >= 60:
            self._refresh_zones(frame.shape)
        t = time.perf_counter()
        detections: List[Detection] = self._detector.detect(frame)
        t = self._lap("yolo", t)
        for detection in detections:
            name = str(detection.class_name).strip().lower() or "unknown"
            self._class_counts[name] = self._class_counts.get(name, 0) + 1
        bboxes = [d.bbox for d in detections]
        tracked = self._tracker.update(bboxes)
        bbox_to_detection = {d.bbox: d for d in detections}

        for track_id, bbox in tracked.items():
            detection = bbox_to_detection.get(bbox)
            if detection is not None:
                self._track_confidences.setdefault(track_id, []).append(detection.confidence)

        self._current_tracked = tracked
        summary = {"detections": len(detections), "tracked": len(tracked), "events": []}
        faces = []

        if self._fence:
            entered = self._fence.check(tracked)
            for track_id in entered:
                self._report("intrusion", "critical", self._avg_confidence(track_id), f"Track {track_id} entered restricted zone", frame=frame)
                self._event_counts["intrusion"] = self._event_counts.get("intrusion", 0) + 1
                summary["events"].append({"type": "intrusion", "track_id": track_id})

        t = time.perf_counter()
        if self._anpr:
            for track_id, bbox in tracked.items():
                detection = bbox_to_detection.get(bbox)
                if detection is None or detection.class_name not in VEHICLE_CLASSES:
                    continue
                if not self._anpr_can_emit(track_id):
                    continue

                plate_text = self._anpr.read_plate_for_vehicle(
                    frame, bbox, track_id=track_id, frame_index=self._frame_index
                )
                if not plate_text:
                    continue

                self._anpr_last_emitted[track_id] = self._frame_index
                self._report("anpr", "high", detection.confidence, f"Vehicle ({detection.class_name}, track {track_id}) — plate {plate_text}", frame=frame)
                self._event_counts["anpr"] = self._event_counts.get("anpr", 0) + 1
                summary["events"].append({"type": "anpr", "track_id": track_id, "plate": plate_text})

        t = self._lap("anpr", t)
        if self._face_detector:
            if self._frame_index % self._face_every_n == 0:
                # Fresh detection: only these frames count as face events.
                self._last_faces = self._face_detector.detect(frame)
                if self._last_faces:
                    self._event_counts["face"] = self._event_counts.get("face", 0) + len(self._last_faces)
                    summary["events"].append({"type": "face", "count": len(self._last_faces)})
            # Frames in between just redraw the most recent boxes.
            faces = self._last_faces
        t = self._lap("face", t)

        if self._activity_detector:
            class_by_id = {tid: bbox_to_detection.get(bbox).class_name for tid,bbox in tracked.items() if bbox_to_detection.get(bbox)}
            for event in self._activity_detector.update(tracked, class_by_id):
                severity = _severity_for(event["activity"])
                self._report("activity", severity, self._avg_confidence(event["track_id"]),
                             f"Track {event['track_id']} — {event['activity']}", frame=frame)
                self._event_counts["activity"] = self._event_counts.get("activity", 0) + 1
                summary["events"].append(event)

        self._draw_overlay(frame, detections, faces, summary["events"])
        self._lap("other", t)
        self._log_profile()
        return summary

    def _avg_confidence(self, track_id: int) -> float:
        """Real average of this track's own detection confidences so far —
        replaces the old fixed placeholder numbers."""
        history = self._track_confidences.get(track_id)
        if history:
            return round(sum(history) / len(history), 2)
        all_scores = [c for scores in self._track_confidences.values() for c in scores]
        return round(sum(all_scores) / len(all_scores), 2) if all_scores else 0.0

    def analysis_summary(self) -> dict:
        """Return accumulated recorded-video findings for persistence/history."""
        return {
            "objects": dict(sorted(self._class_counts.items(), key=lambda item: (-item[1], item[0]))),
            "events": dict(sorted(self._event_counts.items(), key=lambda item: (-item[1], item[0]))),
        }

    def run(self, source: Optional[str] = None, process_every_n: int = 1, loop: bool = False):
        """
        source: webcam index or video file path (falls back to .env
                CAMERA_SOURCE if not given).
        loop:   if True and the source is a video file that reaches its
                end, reopen it and keep going — useful for a short demo
                clip you want to keep running during a live demo instead
                of the pipeline just stopping.
        """
        source = source or get_settings().camera_source
        while True:
            try:
                with VideoStream(source) as stream:
                    processor = FrameProcessor(stream, process_every_n=process_every_n)
                    for frame in processor.frames():
                        self.process_frame(frame)
                        if self._frame_callback is not None:
                            self._frame_callback(frame)
            except RuntimeError as exc:
                # Do not spin or crash immediately on a temporary camera
                # outage. A persistent worker gives the operator time to
                # restore an RTSP camera/network connection.
                log.error("Video source unavailable: %s", exc)
                if not loop:
                    time.sleep(2)
                    continue
            if not loop:
                return
            log.info("Video source ended — looping (--loop was set).")
