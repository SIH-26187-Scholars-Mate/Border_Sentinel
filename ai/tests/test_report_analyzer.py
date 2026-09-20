"""
Tests ai/video/report_analyzer.py's aggregation logic — object counting,
intrusion flagging, and the summary sentence — using fake
detector/face/anpr components (no torch/ultralytics needed), the same
pattern test_pipeline_anpr.py uses.
"""
import numpy as np

from ai.detection.detector import Detection
from ai.video.report_analyzer import VideoReportAnalyzer

FENCE_ZONE = [(100, 100), (400, 100), (400, 400), (100, 400)]


class _FakeDetector:
    """Returns a fixed set of detections regardless of the frame."""

    def __init__(self, detections):
        self._detections = detections

    def detect(self, frame):
        return self._detections


class _NoFaces:
    def detect(self, frame):
        return []


class _AlwaysOneFace:
    def detect(self, frame):
        return [(10, 10, 20, 20)]


class _FakeANPR:
    """Always 'reads' a fixed plate for any vehicle bbox it's given."""

    def __init__(self, plate="DL7CAF1234"):
        self._plate = plate

    def read_plate_for_vehicle(self, frame, bbox):
        return self._plate


def _blank_frame():
    return np.zeros((300, 500, 3), dtype=np.uint8)


def test_counts_unique_objects_not_per_frame_detections():
    # A person bbox that stays put for 5 frames should count as ONE person,
    # not five.
    detector = _FakeDetector([Detection("person", 0.9, (10, 10, 40, 40))])
    analyzer = VideoReportAnalyzer(detector=detector, face_detector=_NoFaces())

    for _ in range(5):
        analyzer.process_frame(_blank_frame(), fps=25.0)

    report = analyzer.build_report(fps=25.0)
    assert report["object_counts"] == {"person": 1}
    assert report["frames_analyzed"] == 5
    assert "1 person" in report["summary"]


def test_intrusion_into_fence_zone_is_reported_once():
    # Track starts outside the zone, then moves inside on frame 2 and stays.
    class _MovingDetector:
        def __init__(self):
            self._frame = 0

        def detect(self, frame):
            self._frame += 1
            if self._frame == 1:
                return [Detection("person", 0.9, (0, 0, 20, 20))]  # centroid (10,10) — outside
            return [Detection("person", 0.9, (240, 240, 260, 260))]  # centroid (250,250) — inside

    analyzer = VideoReportAnalyzer(
        fence_polygon=FENCE_ZONE, detector=_MovingDetector(), face_detector=_NoFaces()
    )
    for _ in range(4):
        analyzer.process_frame(_blank_frame(), fps=25.0)

    report = analyzer.build_report(fps=25.0)
    assert len(report["intrusions"]) == 1
    assert "intrusion" in report["summary"].lower()


def test_vehicle_plate_is_read_and_deduped():
    detector = _FakeDetector([Detection("car", 0.9, (50, 50, 200, 200))])
    analyzer = VideoReportAnalyzer(
        detector=detector, face_detector=_NoFaces(), anpr_processor=_FakeANPR("DL7CAF1234")
    )
    for _ in range(10):
        analyzer.process_frame(_blank_frame(), fps=25.0)

    report = analyzer.build_report(fps=25.0)
    # Cooldown means the same plate on the same track is only recorded once.
    # confidence is the real average of that track's own detections (here
    # every frame reports 0.9, so the average is 0.9) — not a placeholder.
    assert report["vehicles"] == [{"plate": "DL7CAF1234", "time_seconds": 0.04, "confidence": 0.9}]
    assert "DL7CAF1234" in report["summary"]


def test_faces_are_counted_by_frame():
    analyzer = VideoReportAnalyzer(detector=_FakeDetector([]), face_detector=_AlwaysOneFace())
    for _ in range(3):
        analyzer.process_frame(_blank_frame(), fps=25.0)

    report = analyzer.build_report(fps=25.0)
    assert report["faces_detected_frames"] == 3
    assert "face" in report["summary"].lower()


def test_empty_clip_reports_nothing_detected():
    analyzer = VideoReportAnalyzer(detector=_FakeDetector([]), face_detector=_NoFaces())
    analyzer.process_frame(_blank_frame(), fps=25.0)

    report = analyzer.build_report(fps=25.0)
    assert report["object_counts"] == {}
    assert report["summary"] == "No objects were detected in this clip."


def test_vehicle_tracks_list_plate_or_none_per_vehicle():
    # Two vehicles far apart (two separate tracks) and one person. The fake
    # ANPR only "reads" a plate for the first vehicle's crop.
    class _PlateForLeftCarOnly:
        def read_plate_for_vehicle(self, frame, bbox):
            return "MH12AB1234" if bbox[0] < 250 else None

    detector = _FakeDetector([
        Detection("car", 0.9, (10, 50, 180, 200)),
        Detection("truck", 0.9, (300, 50, 480, 200)),
        Detection("person", 0.9, (200, 10, 230, 60)),
    ])
    analyzer = VideoReportAnalyzer(
        detector=detector, face_detector=_NoFaces(), anpr_processor=_PlateForLeftCarOnly()
    )
    for _ in range(20):
        analyzer.process_frame(_blank_frame(), fps=25.0)

    report = analyzer.build_report(fps=25.0)
    rows = {(v["type"], v["plate"]) for v in report["vehicle_tracks"]}
    assert rows == {("car", "MH12AB1234"), ("truck", None)}
    # People are not vehicles, so they never get a plate row.
    assert all(v["type"] != "person" for v in report["vehicle_tracks"])


def test_vehicle_gives_up_after_max_attempts_but_still_listed_as_none():
    from ai.video import report_analyzer as ra

    class _CountingANPR:
        calls = 0

        def read_plate_for_vehicle(self, frame, bbox):
            _CountingANPR.calls += 1
            return None

    detector = _FakeDetector([Detection("car", 0.9, (50, 50, 250, 250))])
    analyzer = VideoReportAnalyzer(
        detector=detector, face_detector=_NoFaces(), anpr_processor=_CountingANPR()
    )
    for _ in range(200):
        analyzer.process_frame(_blank_frame(), fps=25.0)

    assert _CountingANPR.calls == ra.ANPR_MAX_ATTEMPTS_PER_TRACK
    assert analyzer.build_report(fps=25.0)["vehicle_tracks"] == [
        {"track_id": 1, "type": "car", "plate": None}
    ]
