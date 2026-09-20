"""Robust OpenCV video source wrapper for webcams, RTSP streams and files."""
import time

import cv2

from ai.utils.logger import get_logger

log = get_logger(__name__)


class VideoStream:
    def __init__(self, source: str, reconnect_attempts: int = 5, reconnect_delay: float = 1.0):
        self.source = source
        self._source = int(source) if str(source).isdigit() else source
        self._reconnect_attempts = max(1, reconnect_attempts)
        self._reconnect_delay = max(0.1, reconnect_delay)
        self._cap = None
        self._open()

    def _open(self):
        self._cap = cv2.VideoCapture(self._source)
        # A few RTSP/webcam backends need a moment before isOpened() settles.
        if not self._cap.isOpened():
            self._cap.release()
            self._cap = None
            raise RuntimeError(f"Could not open video source: {self.source}")
        log.info("Opened video source: %s", self.source)

    def _reconnect(self) -> bool:
        if self._cap is not None:
            self._cap.release()
            self._cap = None
        for attempt in range(1, self._reconnect_attempts + 1):
            time.sleep(self._reconnect_delay * min(attempt, 3))
            try:
                self._open()
                log.info("Reconnected video source %s (attempt %d)", self.source, attempt)
                return True
            except RuntimeError as exc:
                log.warning("Video source reconnect %d/%d failed: %s", attempt, self._reconnect_attempts, exc)
        return False

    @property
    def is_live_source(self) -> bool:
        """True for webcams/RTSP/network streams, false for local video files."""
        value = str(self.source).lower()
        return str(self.source).isdigit() or value.startswith((
            "rtsp://", "rtsps://", "http://", "https://", "udp://", "tcp://"
        ))

    def read(self):
        """Return the next frame, reconnecting only live sources."""
        if self._cap is None:
            return False, None
        ok, frame = self._cap.read()
        if ok:
            return True, frame

        # A local file reaching EOF is normal. Do not reopen it: uploaded
        # analysis must terminate so its completion handler can persist history.
        if not self.is_live_source:
            log.info("Recorded video reached EOF: %s", self.source)
            return False, None

        log.warning("Read failed for live video source %s; attempting reconnect", self.source)
        if self._reconnect():
            ok, frame = self._cap.read()
            if ok:
                return True, frame
        return False, None

    def fps(self) -> float:
        return self._cap.get(cv2.CAP_PROP_FPS) if self._cap is not None else 0.0

    def release(self):
        if self._cap is not None:
            self._cap.release()
            self._cap = None
            log.info("Released video source: %s", self.source)

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()
