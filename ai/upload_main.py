"""
ai/upload_main.py

Standalone video-report service backing the dashboard's "Analyze" page.
The backend starts this automatically on its own startup (see
backend/app/services/analysis_worker.py) and the frontend talks to it
directly over HTTP.

This only exposes the upload -> background-analysis -> report API — no
live MJPEG streaming, so it never competes with a live camera worker
(ai/main.py) for a preview port, and it doesn't need any camera to be
actively running (the camera it saves alerts against just needs to exist).
"""
from __future__ import annotations

import argparse

import uvicorn

from ai.utils.config import get_settings
from ai.utils.logger import get_logger
from ai.video.upload_server import create_upload_app

log = get_logger(__name__)


def main() -> None:
    settings = get_settings()
    parser = argparse.ArgumentParser(description="Border Sentinel video-report service")
    parser.add_argument("--upload-api-port", type=int, default=8002)
    args = parser.parse_args()

    app = create_upload_app()
    config = uvicorn.Config(
        app,
        host=settings.preview_host,
        port=args.upload_api_port,
        log_level="warning",
    )
    server = uvicorn.Server(config)

    log.info("Video report service listening on :%s", args.upload_api_port)
    server.run()


if __name__ == "__main__":
    main()
