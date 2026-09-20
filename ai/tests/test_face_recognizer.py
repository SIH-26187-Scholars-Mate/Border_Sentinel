"""
Tests for face recognition: gallery matching, the alert rules, and the way
the live pipeline / recorded-video analyzer turn matches into alerts.

The neural models (YuNet / SFace) are NOT needed here: a small fake
recognizer supplies face boxes and embeddings, so everything after that
point (matching, thresholds, alert rules, debouncing) is real code.
"""
from unittest.mock import patch

import numpy as np

from ai.detection.detector import Detection
from ai.face.face_recognizer import (
    AUTHORIZED, UNKNOWN, UNVERIFIED, WATCHLIST, FaceMatch, FaceRecognizer, alert_for, track_for_face,
)
from ai.pipeline import Pipeline
from ai.video.report_analyzer import VideoReportAnalyzer

CAM = "11111111-1111-1111-1111-111111111111"


def _vec(i, n=8):
    v = np.zeros(n, dtype=np.float32)
    v[i] = 1.0
    return v


class _FakeRecognizer(FaceRecognizer):
    """script: one list per identify() call of (bbox, feature) pairs."""

    def __init__(self, script):
        super().__init__(load_models=False)
        self._ready = True
        self._script = script
        self._call = -1
        self._current = []

    def _detect_faces(self, image):
        self._call += 1
        self._current = self._script[min(self._call, len(self._script) - 1)]
        return [np.array([x, y, w, h] + [0.0] * 10 + [0.99], dtype=np.float32)
                for (x, y, w, h), _ in self._current]

    def _embed_face(self, image, row):
        for (x, _y, _w, _h), feat in self._current:
            if int(row[0]) == x:
                return feat
        raise AssertionError("unknown face row")


def _gallery(rec):
    rec.add_identity("alice", AUTHORIZED, _vec(0))
    rec.add_identity("bob", AUTHORIZED, _vec(1))
    rec.add_identity("mallory", WATCHLIST, _vec(2))
    return rec


# ---------------------------------------------------------------- matching
def test_match_feature_finds_the_right_person_and_group():
    rec = _gallery(_FakeRecognizer([[]]))
    name, group, score = rec.match_feature(_vec(0) * 3 + _vec(5) * 0.1)  # ~alice
    assert (name, group) == ("alice", AUTHORIZED) and score > 0.9
    name, group, _ = rec.match_feature(_vec(2))
    assert (name, group) == ("mallory", WATCHLIST)


def test_match_feature_below_threshold_is_unknown():
    rec = _gallery(_FakeRecognizer([[]]))
    name, group, score = rec.match_feature(_vec(6))  # orthogonal to everyone
    assert name is None and group == UNKNOWN and score < 0.363


def test_empty_gallery_never_matches():
    rec = _FakeRecognizer([[]])
    assert rec.match_feature(_vec(0)) == (None, UNKNOWN, 0.0)
    assert not rec.has_authorized_gallery


def test_tiny_faces_are_unverified_not_unknown():
    rec = _gallery(_FakeRecognizer([[((10, 10, 20, 20), _vec(6))]]))  # 20 px wide
    (match,) = rec.identify(np.zeros((200, 200, 3), np.uint8))
    assert match.group == UNVERIFIED
    assert alert_for(match, has_authorized_gallery=True) is None


# ------------------------------------------------------------- alert rules
def _m(group, name=None, score=0.8):
    return FaceMatch((0, 0, 80, 80), group, name, score, 0.99)


def test_alert_rules():
    watch = alert_for(_m(WATCHLIST, "mallory", 0.71), True)
    assert watch.severity == "critical" and "mallory" in watch.description
    unknown = alert_for(_m(UNKNOWN, None, 0.1), True)
    assert unknown.severity == "high" and "Unrecognized" in unknown.description
    # No authorized list enrolled -> unknown faces are labelled, never alerted.
    assert alert_for(_m(UNKNOWN, None, 0.1), False) is None
    assert alert_for(_m(AUTHORIZED, "alice"), True) is None


def test_track_for_face_uses_person_boxes_only():
    tracked = {1: (0, 0, 300, 300), 2: (90, 40, 210, 260)}
    classes = {1: "car", 2: "person"}
    assert track_for_face((120, 60, 40, 40), tracked, classes) == 2   # centre inside the person
    assert track_for_face((10, 10, 20, 20), tracked, classes) is None  # only inside the car


# ---------------------------------------------------------- live pipeline
class _PersonDetector:
    def __init__(self, bbox=(50, 20, 250, 280)):
        self._bbox = bbox

    def detect(self, frame):
        return [Detection("person", 0.9, self._bbox)]


class _StaticTracker:
    def update(self, bboxes):
        return {1: bboxes[0]} if bboxes else {}


def _pipeline(script):
    return Pipeline(
        camera_id=CAM, run_anpr=False, run_activity=False, face_every_n=1,
        detector=_PersonDetector(), tracker=_StaticTracker(),
        face_recognizer=_gallery(_FakeRecognizer(script)),
    )


def _run(pipeline, frames=6):
    frame = np.zeros((300, 300, 3), np.uint8)
    with patch("ai.pipeline.send_detection") as send:
        send.return_value = {"id": "x"}
        for _ in range(frames):
            pipeline.process_frame(frame.copy())
    return send.call_args_list


def test_unrecognized_person_raises_one_intrusion_alert_after_confirmation():
    calls = _run(_pipeline([[((100, 60, 80, 80), _vec(6))]]), frames=6)  # unknown every pass
    assert len(calls) == 1                                    # once per tracked person
    kw = calls[0].kwargs
    assert kw["alert_type"] == "intrusion" and kw["severity"] == "high"


def test_single_unknown_frame_does_not_alert():
    # unknown once, then recognised as alice: the blip must not raise an alert
    script = [[((100, 60, 80, 80), _vec(6))], [((100, 60, 80, 80), _vec(0))]]
    assert _run(_pipeline(script), frames=4) == []


def test_recognised_person_never_triggers_unknown_even_if_later_frames_blur():
    script = [[((100, 60, 80, 80), _vec(0))]] + [[((100, 60, 80, 80), _vec(6))]] * 5
    assert _run(_pipeline(script), frames=6) == []


def test_watchlist_match_raises_critical_alert_with_cooldown():
    calls = _run(_pipeline([[((100, 60, 80, 80), _vec(2))]]), frames=10)
    assert len(calls) == 1                                    # cooldown stops repeats
    kw = calls[0].kwargs
    assert kw["severity"] == "critical" and "mallory" in kw["description"]


# --------------------------------------------------------------- analyzer
class _NoFaces:
    def detect(self, frame):
        return []


def _analyze(script, frames=6):
    analyzer = VideoReportAnalyzer(
        detector=_PersonDetector(), tracker=_StaticTracker(), face_detector=_NoFaces(),
        face_recognizer=_gallery(_FakeRecognizer(script)),
    )
    for _ in range(frames):
        analyzer.process_frame(np.zeros((300, 300, 3), np.uint8), fps=25.0)
    return analyzer.build_report(fps=25.0)


def test_report_lists_recognized_watchlist_and_unrecognized():
    report = _analyze([[((100, 60, 80, 80), _vec(0))]])
    ids = report["face_identities"]
    assert ids["recognition_active"] is True
    assert [p["name"] for p in ids["authorized"]] == ["alice"]
    assert ids["watchlist"] == [] and ids["unrecognized"] == []
    assert "Recognized: alice" in report["summary"]

    report = _analyze([[((100, 60, 80, 80), _vec(2))]])
    assert [p["name"] for p in report["face_identities"]["watchlist"]] == ["mallory"]
    assert "WATCHLIST" in report["summary"]

    report = _analyze([[((100, 60, 80, 80), _vec(6))]])
    assert len(report["face_identities"]["unrecognized"]) == 1
    assert "1 unrecognized person" in report["summary"]


def test_report_without_recognition_models_falls_back_to_plain_detection():
    analyzer = VideoReportAnalyzer(detector=_PersonDetector(), face_detector=_NoFaces(),
                                   face_recognizer=FaceRecognizer(load_models=False))
    analyzer.process_frame(np.zeros((300, 300, 3), np.uint8), fps=25.0)
    assert analyzer.build_report(25.0)["face_identities"]["recognition_active"] is False
