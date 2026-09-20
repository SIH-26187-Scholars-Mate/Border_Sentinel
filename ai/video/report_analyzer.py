"""
ai/video/report_analyzer.py

Powers the simplified "Analyze" report: upload a clip, get back plain
text/JSON describing what was in it — objects seen, vehicle plates read,
faces spotted, and intrusion/suspicious-activity events — with no
dependency on the backend, a saved camera, or the live MJPEG preview.

This intentionally does NOT reuse ai/pipeline.py's Pipeline class, because
Pipeline is built to stream alerts into the backend for a live camera. This
analyzer runs the same underlying building blocks (Detector, tracker, face
detector, activity detector, ANPR, virtual fence) directly, purely to build
one summary object once the whole clip has been processed.
"""
from __future__ import annotations

from collections import Counter
from typing import Dict, List, Optional, Tuple

import numpy as np

from ai.activity.activity_detector import ActivityDetector
from ai.anpr.anpr_processor import ANPRProcessor
from ai.detection.detector import Detection, Detector
from ai.face.face_detector import FaceDetector
from ai.face.face_recognizer import (
    ALERT_COOLDOWN_FRAMES, AUTHORIZED, UNKNOWN_CONFIRMATIONS, WATCHLIST,
    FaceRecognizer, alert_for, track_for_face,
)
from ai.intrusion.virtual_fence import VirtualFence
from ai.tracking.tracker import CentroidTracker
from ai.utils.logger import get_logger
from ai.video.frame_processor import FrameProcessor
from ai.video.video_stream import VideoStream

log = get_logger(__name__)

VEHICLE_CLASSES = {"car", "truck", "bus", "motorcycle"}
# Plate reading is per vehicle track: keep trying until a plate is read, but
# not every frame (OCR is slow) and not forever (a vehicle that never shows a
# readable plate is reported as plate "None").
ANPR_RETRY_EVERY_FRAMES = 8
ANPR_MAX_ATTEMPTS_PER_TRACK = 6
# Vehicles narrower than this (in processed-frame pixels) are too small for
# their plate to be legible, so don't spend OCR time on them.
ANPR_MIN_VEHICLE_WIDTH_PX = 80


class VideoReportAnalyzer:
    """Feed it frames one at a time via process_frame(), then call
    build_report() once for a plain-language + structured summary."""

    def __init__(
        self,
        fence_polygon: Optional[List[Tuple[float, float]]] = None,
        detector: Optional[Detector] = None,
        tracker: Optional[CentroidTracker] = None,
        face_detector: Optional[FaceDetector] = None,
        activity_detector: Optional[ActivityDetector] = None,
        anpr_processor: Optional[ANPRProcessor] = None,
        face_every_n: int = 1,
        face_recognizer: Optional[FaceRecognizer] = None,
    ):
        self._face_every_n = max(1, int(face_every_n))
        # Who-is-this recognition; inactive (plain detection) if models are missing.
        self._recognizer = face_recognizer if face_recognizer is not None else FaceRecognizer()
        self._authorized_seen: Dict[str, float] = {}          # name -> first time seen (s)
        self._watchlist_seen: Dict[str, dict] = {}            # name -> {time_seconds, confidence}
        self._unrecognized: Dict[object, dict] = {}           # track_id (or bucket) -> {time_seconds, confidence}
        self._authorized_tracks: set = set()
        self._unknown_streak: Dict[object, int] = {}
        self._last_face_found = False
        self._detector = detector if detector is not None else Detector()
        self._tracker = tracker if tracker is not None else CentroidTracker()
        self._face_detector = face_detector if face_detector is not None else FaceDetector()
        self._activity_detector = activity_detector if activity_detector is not None else ActivityDetector()
        self._anpr = anpr_processor if anpr_processor is not None else ANPRProcessor()
        self._fence = VirtualFence(fence_polygon) if fence_polygon else None

        self._seen_tracks: Dict[int, str] = {}      # track_id -> class of its first sighting
        self._track_plates: Dict[int, str] = {}      # vehicle track_id -> plate text read for it
        self._anpr_attempts: Dict[int, int] = {}     # track_id -> OCR attempts made so far
        self._anpr_last_try: Dict[int, int] = {}     # track_id -> frame index of last attempt
        self._seen_plates: Dict[str, float] = {}     # plate text -> first time seen (seconds)
        self._seen_plate_confidences: Dict[str, float] = {}  # plate text -> detector confidence at read time
        self._track_confidences: Dict[int, List[float]] = {}  # track_id -> confidence history
        self._all_confidences: List[float] = []      # every real detection confidence in the clip
        self._intrusions: List[dict] = []
        self._activities: List[dict] = []
        self._frames_with_face = 0
        self._frame_index = 0

    def _time_s(self, fps: float) -> float:
        return round(self._frame_index / fps, 2) if fps > 0 else float(self._frame_index)

    def _avg_confidence(self, track_id: int) -> float:
        """Real average of this track's own detection confidences so far —
        not a placeholder. Falls back to the clip-wide average on the rare
        chance a track has no recorded confidence yet."""
        history = self._track_confidences.get(track_id)
        if history:
            return round(sum(history) / len(history), 2)
        if self._all_confidences:
            return round(sum(self._all_confidences) / len(self._all_confidences), 2)
        return 0.0

    def _should_try_plate(self, track_id: int, bbox) -> bool:
        if track_id in self._track_plates:
            return False  # already have this vehicle's plate
        if self._anpr_attempts.get(track_id, 0) >= ANPR_MAX_ATTEMPTS_PER_TRACK:
            return False  # gave up: report "None" for this vehicle
        if (bbox[2] - bbox[0]) < ANPR_MIN_VEHICLE_WIDTH_PX:
            return False
        last = self._anpr_last_try.get(track_id)
        return last is None or (self._frame_index - last) >= ANPR_RETRY_EVERY_FRAMES

    def process_frame(self, frame: np.ndarray, fps: float) -> None:
        self._frame_index += 1

        detections: List[Detection] = self._detector.detect(frame)
        bboxes = [d.bbox for d in detections]
        tracked = self._tracker.update(bboxes)
        bbox_to_detection = {d.bbox: d for d in detections}

        # Record each track's class the first time we see it, so the final
        # report counts unique objects, not one count per frame they linger.
        # Also record this frame's real confidence for every live track, so
        # every alert can report an actual average instead of a fixed number.
        for track_id, bbox in tracked.items():
            detection = bbox_to_detection.get(bbox)
            if detection is None:
                continue
            if track_id not in self._seen_tracks:
                self._seen_tracks[track_id] = detection.class_name
            self._track_confidences.setdefault(track_id, []).append(detection.confidence)
            self._all_confidences.append(detection.confidence)

        if self._fence is not None:
            for track_id in self._fence.check(tracked):
                self._intrusions.append({
                    "track_id": track_id,
                    "time_seconds": self._time_s(fps),
                    "confidence": self._avg_confidence(track_id),
                })

        for track_id, bbox in tracked.items():
            detection = bbox_to_detection.get(bbox)
            if detection is None or detection.class_name not in VEHICLE_CLASSES:
                continue
            if not self._should_try_plate(track_id, bbox):
                continue
            plate_text = self._anpr.read_plate_for_vehicle(frame, bbox)
            self._anpr_attempts[track_id] = self._anpr_attempts.get(track_id, 0) + 1
            self._anpr_last_try[track_id] = self._frame_index
            if not plate_text:
                continue
            self._track_plates[track_id] = plate_text
            self._seen_plates.setdefault(plate_text, self._time_s(fps))
            self._seen_plate_confidences.setdefault(plate_text, self._avg_confidence(track_id))

        class_by_id = {
            tid: bbox_to_detection[bbox].class_name
            for tid, bbox in tracked.items()
            if bbox_to_detection.get(bbox)
        }

        # Face work is the slowest per-frame step; run it every Nth frame and
        # carry the last answer over so faces_detected_frames still reflects
        # how many frames had a face on screen.
        if self._frame_index % self._face_every_n == 0 or self._frame_index == 1:
            if self._recognizer.ready:
                matches = self._recognizer.identify(frame)
                self._last_face_found = bool(matches)
                self._record_face_identities(matches, tracked, class_by_id, fps)
            else:
                self._last_face_found = bool(self._face_detector.detect(frame))
        if self._last_face_found:
            self._frames_with_face += 1

        for event in self._activity_detector.update(tracked, class_by_id):
            self._activities.append({
                "track_id": event["track_id"],
                "activity": event["activity"],
                "time_seconds": self._time_s(fps),
                "confidence": self._avg_confidence(event["track_id"]),
            })

    def _record_face_identities(self, matches, tracked, class_by_id, fps: float) -> None:
        """Collect who was recognised / not recognised, one entry per person."""
        seen_unknown_keys = set()
        has_authorized = self._recognizer.has_authorized_gallery
        now = self._time_s(fps)
        for match in matches:
            track_id = track_for_face(match.bbox, tracked, class_by_id)
            if match.group == AUTHORIZED:
                self._authorized_seen.setdefault(match.name, now)
                if track_id is not None:
                    self._authorized_tracks.add(track_id)
                    self._unknown_streak.pop(track_id, None)
                continue
            alert = alert_for(match, has_authorized)
            if alert is None:
                continue
            if alert.kind == "watchlist":
                entry = self._watchlist_seen.setdefault(
                    match.name, {"time_seconds": now, "confidence": round(alert.confidence, 2)})
                entry["confidence"] = max(entry["confidence"], round(alert.confidence, 2))
                continue
            # unrecognized person: needs consecutive confirmations, and never
            # for a person already recognised as authorized on the same track.
            if track_id is not None and track_id in self._authorized_tracks:
                continue
            # Faces we can't tie to a tracked person share a time bucket so a
            # lingering unknown face isn't reported on every pass.
            key = track_id if track_id is not None else f"untracked-{self._frame_index // ALERT_COOLDOWN_FRAMES}"
            seen_unknown_keys.add(key)
            self._unknown_streak[key] = self._unknown_streak.get(key, 0) + 1
            if self._unknown_streak[key] >= UNKNOWN_CONFIRMATIONS and key not in self._unrecognized:
                self._unrecognized[key] = {"time_seconds": now, "confidence": round(alert.confidence, 2)}
        for key in [k for k in self._unknown_streak if k not in seen_unknown_keys]:
            self._unknown_streak.pop(key, None)

    def build_report(self, fps: float) -> dict:
        object_counts = dict(Counter(self._seen_tracks.values()))
        avg_confidence = (
            round(sum(self._all_confidences) / len(self._all_confidences), 2)
            if self._all_confidences else 0.0
        )

        summary_bits: List[str] = []
        if object_counts:
            parts = ", ".join(
                f"{count} {name}{'s' if count != 1 else ''}" for name, count in object_counts.items()
            )
            summary_bits.append(f"Detected {parts}.")
        else:
            summary_bits.append("No objects were detected in this clip.")
        if self._seen_plates:
            plates = ", ".join(self._seen_plates.keys())
            summary_bits.append(f"{len(self._seen_plates)} vehicle plate(s) read: {plates}.")
        if self._frames_with_face:
            summary_bits.append(f"A face was visible in {self._frames_with_face} frame(s).")
        if self._recognizer.ready:
            if self._authorized_seen:
                summary_bits.append("Recognized: " + ", ".join(self._authorized_seen) + ".")
            if self._watchlist_seen:
                summary_bits.append("WATCHLIST match: " + ", ".join(self._watchlist_seen) + " (verify manually).")
            if self._unrecognized:
                n = len(self._unrecognized)
                summary_bits.append(f"{n} unrecognized person{'s' if n != 1 else ''} (not in the authorized list).")
        if self._intrusions:
            summary_bits.append(f"{len(self._intrusions)} intrusion event(s) into the restricted zone were flagged.")
        if self._activities:
            summary_bits.append(f"{len(self._activities)} suspicious activity event(s) were flagged.")

        # One row per vehicle (car/truck/bus/motorcycle) with the plate read
        # for it, or None when no plate could be read.
        vehicle_tracks = [
            {
                "track_id": tid,
                "type": cls,
                "plate": self._track_plates.get(tid),
            }
            for tid, cls in sorted(self._seen_tracks.items())
            if cls in VEHICLE_CLASSES
        ]

        return {
            "frames_analyzed": self._frame_index,
            "duration_seconds": self._time_s(fps),
            "object_counts": object_counts,
            "avg_detection_confidence": avg_confidence,
            "vehicles": [
                {
                    "plate": plate,
                    "time_seconds": t,
                    "confidence": self._seen_plate_confidences.get(plate, avg_confidence),
                }
                for plate, t in self._seen_plates.items()
            ],
            "face_identities": {
                "recognition_active": self._recognizer.ready,
                "authorized": [{"name": n, "time_seconds": t} for n, t in self._authorized_seen.items()],
                "watchlist": [{"name": n, **info} for n, info in self._watchlist_seen.items()],
                "unrecognized": [
                    {"track_id": (k if isinstance(k, int) else None), **info}
                    for k, info in self._unrecognized.items()
                ],
            },
            "vehicle_tracks": vehicle_tracks,
            "faces_detected_frames": self._frames_with_face,
            "intrusions": self._intrusions,
            "activities": self._activities,
            "summary": " ".join(summary_bits),
        }


def analyze_video_file(
    path: str,
    fence_polygon: Optional[List[Tuple[float, float]]] = None,
    process_every_n: int = 1,
    face_every_n: int = 3,
    **analyzer_kwargs,
) -> dict:
    """Opens `path`, runs every (sampled) frame through VideoReportAnalyzer,
    and returns the final report dict. Raises RuntimeError if the file
    can't be opened (bad path, corrupt/unsupported video, etc.)."""
    analyzer = VideoReportAnalyzer(fence_polygon=fence_polygon, face_every_n=face_every_n, **analyzer_kwargs)
    with VideoStream(path) as stream:
        fps = stream.fps() or 25.0
        processor = FrameProcessor(stream, process_every_n=process_every_n)
        # analyzer counts processed frames, so when frames are skipped the
        # effective rate is lower — otherwise reported timestamps are too small.
        effective_fps = fps / max(1, process_every_n)
        for frame in processor.frames():
            analyzer.process_frame(frame, effective_fps)
    return analyzer.build_report(effective_fps)
