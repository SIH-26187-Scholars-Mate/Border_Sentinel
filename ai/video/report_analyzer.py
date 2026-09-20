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
from ai.intrusion.virtual_fence import VirtualFence
from ai.tracking.tracker import CentroidTracker
from ai.utils.logger import get_logger
from ai.video.frame_processor import FrameProcessor
from ai.video.video_stream import VideoStream

log = get_logger(__name__)

VEHICLE_CLASSES = {"car", "truck", "bus", "motorcycle"}
# Same cooldown Pipeline uses — don't re-run OCR on the same lingering
# vehicle every single frame.
ANPR_COOLDOWN_FRAMES = 60


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
    ):
        self._detector = detector if detector is not None else Detector()
        self._tracker = tracker if tracker is not None else CentroidTracker()
        self._face_detector = face_detector if face_detector is not None else FaceDetector()
        self._activity_detector = activity_detector if activity_detector is not None else ActivityDetector()
        self._anpr = anpr_processor if anpr_processor is not None else ANPRProcessor()
        self._fence = VirtualFence(fence_polygon) if fence_polygon else None

        self._seen_tracks: Dict[int, str] = {}      # track_id -> class of its first sighting
        self._anpr_last_emitted: Dict[int, int] = {}
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

    def _anpr_can_emit(self, track_id: int) -> bool:
        last = self._anpr_last_emitted.get(track_id)
        return last is None or (self._frame_index - last) > ANPR_COOLDOWN_FRAMES

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
            if not self._anpr_can_emit(track_id):
                continue
            plate_text = self._anpr.read_plate_for_vehicle(frame, bbox)
            if not plate_text:
                continue
            self._anpr_last_emitted[track_id] = self._frame_index
            self._seen_plates.setdefault(plate_text, self._time_s(fps))
            self._seen_plate_confidences.setdefault(plate_text, self._avg_confidence(track_id))

        if self._face_detector.detect(frame):
            self._frames_with_face += 1

        class_by_id = {
            tid: bbox_to_detection[bbox].class_name
            for tid, bbox in tracked.items()
            if bbox_to_detection.get(bbox)
        }
        for event in self._activity_detector.update(tracked, class_by_id):
            self._activities.append({
                "track_id": event["track_id"],
                "activity": event["activity"],
                "time_seconds": self._time_s(fps),
                "confidence": self._avg_confidence(event["track_id"]),
            })

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
        if self._intrusions:
            summary_bits.append(f"{len(self._intrusions)} intrusion event(s) into the restricted zone were flagged.")
        if self._activities:
            summary_bits.append(f"{len(self._activities)} suspicious activity event(s) were flagged.")

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
            "faces_detected_frames": self._frames_with_face,
            "intrusions": self._intrusions,
            "activities": self._activities,
            "summary": " ".join(summary_bits),
        }


def analyze_video_file(
    path: str,
    fence_polygon: Optional[List[Tuple[float, float]]] = None,
    process_every_n: int = 1,
    **analyzer_kwargs,
) -> dict:
    """Opens `path`, runs every (sampled) frame through VideoReportAnalyzer,
    and returns the final report dict. Raises RuntimeError if the file
    can't be opened (bad path, corrupt/unsupported video, etc.)."""
    analyzer = VideoReportAnalyzer(fence_polygon=fence_polygon, **analyzer_kwargs)
    with VideoStream(path) as stream:
        fps = stream.fps() or 25.0
        processor = FrameProcessor(stream, process_every_n=process_every_n)
        for frame in processor.frames():
            analyzer.process_frame(frame, fps)
    return analyzer.build_report(fps)
