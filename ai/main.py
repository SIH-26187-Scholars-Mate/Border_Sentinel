"""
ai/main.py
Run with: python -m ai.main --camera-id <uuid-of-a-real-camera-in-backend>

The camera must already exist in the backend (POST /cameras) — this module
does not create one for you.

Note: this runs the LIVE camera pipeline (+ its own browser preview) only.
The uploaded-video "Analyze" report is a separate, single service that the
backend starts on its own (ai/upload_main.py) — it used to also be bundled
into this module per-camera, which meant every running camera worker tried
to bind the same upload-API port and only the first one ever succeeded.
Don't re-add that here.
"""
import argparse

from ai.pipeline import Pipeline
from ai.utils.logger import get_logger
from ai.utils.config import get_settings
from ai.video.preview_server import PreviewServer

log = get_logger(__name__)


def main():
    parser = argparse.ArgumentParser(description="Border Sentinel AI pipeline")
    parser.add_argument("--camera-id", required=True, help="UUID of an existing backend camera")
    parser.add_argument("--source", default=None, help="Webcam index or video file path (overrides .env CAMERA_SOURCE)")
    parser.add_argument("--every", type=int, default=1, help="Process every Nth frame")
    parser.add_argument("--loop", action="store_true", help="Reopen the source and keep going when a video file ends (for demo clips)")
    parser.add_argument("--preview-port", type=int, default=None, help="Per-camera browser preview port")
    parser.add_argument("--no-preview", action="store_true", help="Disable the browser MJPEG preview server")
    args = parser.parse_args()

    preview = None
    if not args.no_preview:
        settings = get_settings()
        preview_port = args.preview_port or settings.preview_port
        preview = PreviewServer(host=settings.preview_host, port=preview_port)
        preview.start()
        log.info("Camera preview available at http://localhost:%s/stream.mjpg", preview_port)

    try:
        frame_callback = (lambda frame: preview.publish(frame, channel=args.camera_id)) if preview else None
        evidence_callback = (lambda frame, job_id: preview.publish(frame, channel=job_id)) if preview else None
        pipeline = Pipeline(
            camera_id=args.camera_id,
            frame_callback=frame_callback,
            evidence_callback=evidence_callback,
            preview_port=preview_port if preview else None,
        )
        log.info("Starting pipeline for camera %s", args.camera_id)
        pipeline.run(source=args.source, process_every_n=args.every, loop=args.loop)
    finally:
        if preview:
            preview.close()


if __name__ == "__main__":
    main()
