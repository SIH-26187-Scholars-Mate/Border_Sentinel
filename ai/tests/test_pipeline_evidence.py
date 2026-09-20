"""
ai/tests/test_pipeline_evidence.py
Covers the evidence-snapshot wiring added to Pipeline._report(): when a
preview server is available (evidence_callback + preview_port set), a
fired alert should hand its frame off to that callback and report an
image_url pointing at it. With neither set (e.g. --no-preview, or a test
that doesn't care), image_url must stay None exactly as before.

Reuses the same fake-detector-with-readable-plate setup as
test_pipeline_anpr.py to drive a real "anpr" alert through _report().
"""
from unittest.mock import patch

from ai.tests.test_pipeline_anpr import _FakeDetector, _make_frame_with_plate
from ai.pipeline import Pipeline


def test_alert_gets_image_url_when_preview_is_wired_up():
    frame, bbox = _make_frame_with_plate()
    captured = []

    def fake_evidence_callback(frame, job_id):
        captured.append((frame, job_id))

    pipeline = Pipeline(
        camera_id="11111111-1111-1111-1111-111111111111",
        run_face=False,
        run_activity=False,
        run_anpr=True,
        detector=_FakeDetector(bbox),
        evidence_callback=fake_evidence_callback,
        preview_port=8101,
        public_host="localhost",
    )

    with patch("ai.pipeline.send_detection") as mock_send:
        mock_send.return_value = {"id": "fake-alert-id"}
        pipeline.process_frame(frame)

    assert len(captured) == 1  # exactly one alert fired -> exactly one snapshot captured
    job_id = captured[0][1]
    assert job_id.startswith("evidence-")

    _, kwargs = mock_send.call_args
    assert kwargs["image_url"] == f"http://localhost:8101/snapshot.jpg?job={job_id}"


def test_alert_has_no_image_url_without_a_preview_server():
    """Default wiring (no evidence_callback/preview_port, e.g. --no-preview)
    must behave exactly like before this feature existed."""
    frame, bbox = _make_frame_with_plate()
    pipeline = Pipeline(
        camera_id="11111111-1111-1111-1111-111111111111",
        run_face=False,
        run_activity=False,
        run_anpr=True,
        detector=_FakeDetector(bbox),
    )

    with patch("ai.pipeline.send_detection") as mock_send:
        mock_send.return_value = {"id": "fake-alert-id"}
        pipeline.process_frame(frame)

    _, kwargs = mock_send.call_args
    assert kwargs["image_url"] is None


def test_evidence_capture_failure_does_not_block_the_alert():
    """A broken preview server should never take down alert reporting —
    the alert must still be sent, just without a snapshot."""
    frame, bbox = _make_frame_with_plate()

    def broken_evidence_callback(frame, job_id):
        raise RuntimeError("preview server is down")

    pipeline = Pipeline(
        camera_id="11111111-1111-1111-1111-111111111111",
        run_face=False,
        run_activity=False,
        run_anpr=True,
        detector=_FakeDetector(bbox),
        evidence_callback=broken_evidence_callback,
        preview_port=8101,
    )

    with patch("ai.pipeline.send_detection") as mock_send:
        mock_send.return_value = {"id": "fake-alert-id"}
        pipeline.process_frame(frame)  # must not raise

    _, kwargs = mock_send.call_args
    assert kwargs["image_url"] is None
