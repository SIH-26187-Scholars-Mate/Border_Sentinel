"""
ai/video/frame_processor.py
Reads frames from a VideoStream at a controlled processing rate — if
inference is slower than the source frame rate, this skips frames instead
of building an ever-growing backlog.
"""
from typing import Iterator, Optional

import numpy as np

from ai.utils.config import get_settings
from ai.utils.logger import get_logger
from ai.video.low_light import enhance_low_light
from ai.video.video_stream import VideoStream

log = get_logger(__name__)


class FrameProcessor:
    def __init__(self, stream: VideoStream, process_every_n: int = 1):
        """
        process_every_n=1 processes every frame; =3 processes every 3rd frame
        (skipping 2 in between), which is the common way to keep a slow model
        roughly in sync with a fast camera feed.
        """
        self._stream = stream
        self._n = max(1, process_every_n)
        settings = get_settings()
        self._night_vision = settings.night_vision_enabled
        self._brightness_threshold = settings.night_vision_brightness_threshold

    def frames(self) -> Iterator[np.ndarray]:
        i = 0
        while True:
            ok, frame = self._stream.read()
            if not ok:
                if self._stream.is_live_source:
                    # A webcam/RTSP outage is not an instruction to stop the
                    # AI worker. Keep the worker alive so it can reconnect.
                    log.warning("Live source temporarily unavailable; retrying…")
                    continue
                log.info("Video file ended or read failed — stopping.")
                return
            i += 1
            if i % self._n == 0:
                if self._night_vision:
                    frame = enhance_low_light(frame, brightness_threshold=self._brightness_threshold)
                yield frame

    def next_frame(self) -> Optional[np.ndarray]:
        """Pull exactly one processed frame, or None if the stream is exhausted."""
        for frame in self.frames():
            return frame
        return None
