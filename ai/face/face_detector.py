"""
Robust face detection for Border Sentinel.

The previous implementation used a single OpenCV frontal Haar cascade with
one fixed set of parameters. That is fast, but it misses small faces, mildly
angled faces and low-light faces very easily.

This detector stays dependency-light (OpenCV only) but improves recall by:
- using two frontal cascades plus the profile cascade;
- upscaling small/medium frames before detection;
- using CLAHE for uneven/low-light scenes;
- checking a horizontally flipped frame for profile faces;
- merging overlapping detections so the same face is returned once; and
- filtering implausibly small boxes after scaling back to the original frame.

This module performs *face detection*, not identity recognition. It returns
face bounding boxes; it does not claim who a person is.
"""
from typing import List, Tuple

import cv2
import numpy as np

from ai.utils.logger import get_logger

log = get_logger(__name__)

BBox = Tuple[int, int, int, int]  # x, y, w, h


class FaceDetector:
    """OpenCV Haar-based face detector tuned for CCTV/video frames."""

    def __init__(self, min_face_size: int = 24):
        self._min_face_size = max(16, int(min_face_size))
        self._cascades = []

        data_path = getattr(getattr(cv2, "data", None), "haarcascades", None)
        if not data_path or not hasattr(cv2, "CascadeClassifier"):
            log.warning("OpenCV Haar cascade data is unavailable")
            return

        # The alt2 cascade is generally more selective than the default
        # frontal cascade; keeping both gives better coverage on CCTV frames.
        cascade_names = (
            "haarcascade_frontalface_alt2.xml",
            "haarcascade_frontalface_default.xml",
        )
        for name in cascade_names:
            path = data_path + name
            cascade = cv2.CascadeClassifier(path)
            if cascade.empty():
                log.warning("Could not load face cascade from %s", path)
                continue
            self._cascades.append((cascade, False))

        # Profile detection catches side-facing people. We also run it on a
        # horizontally flipped image so both profile directions are covered.
        profile_path = data_path + "haarcascade_profileface.xml"
        profile = cv2.CascadeClassifier(profile_path)
        if not profile.empty():
            self._cascades.append((profile, True))
        else:
            log.warning("Could not load profile face cascade from %s", profile_path)

        if self._cascades:
            log.info("Loaded %d face cascades", len(self._cascades))
        else:
            log.warning("No usable face cascades were loaded")

    @staticmethod
    def _iou(a: BBox, b: BBox) -> float:
        ax, ay, aw, ah = a
        bx, by, bw, bh = b
        x1, y1 = max(ax, bx), max(ay, by)
        x2, y2 = min(ax + aw, bx + bw), min(ay + ah, by + bh)
        inter_w, inter_h = max(0, x2 - x1), max(0, y2 - y1)
        inter = inter_w * inter_h
        if inter == 0:
            return 0.0
        union = aw * ah + bw * bh - inter
        return inter / union if union else 0.0

    @classmethod
    def _deduplicate(cls, boxes: List[BBox], iou_threshold: float = 0.35) -> List[BBox]:
        """Merge overlapping cascade results into one stable box per face."""
        if not boxes:
            return []

        # Prefer larger boxes when two cascades disagree about the same face.
        ordered = sorted(boxes, key=lambda b: b[2] * b[3], reverse=True)
        kept: List[BBox] = []
        for box in ordered:
            if all(cls._iou(box, existing) < iou_threshold for existing in kept):
                kept.append(box)
        return kept

    @staticmethod
    def _prepare(frame: np.ndarray, scale: float):
        """Return an enlarged grayscale image with local contrast enhanced."""
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        if scale != 1.0:
            gray = cv2.resize(gray, None, fx=scale, fy=scale, interpolation=cv2.INTER_CUBIC)
        # CLAHE helps when a CCTV camera has shadows or a bright background.
        clahe = cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8, 8))
        gray = clahe.apply(gray)
        gray = cv2.GaussianBlur(gray, (3, 3), 0)
        return gray

    def _detect_pass(self, image: np.ndarray, scale: float, profile: bool) -> List[BBox]:
        boxes: List[BBox] = []
        min_size = max(self._min_face_size, int(self._min_face_size * scale))

        for cascade, is_profile in self._cascades:
            if is_profile != profile:
                continue
            try:
                found = cascade.detectMultiScale(
                    image,
                    scaleFactor=1.08 if profile else 1.07,
                    minNeighbors=5 if profile else 6,
                    minSize=(min_size, min_size),
                    flags=cv2.CASCADE_SCALE_IMAGE,
                )
            except Exception as exc:
                log.warning("Face cascade failed: %s", exc)
                continue

            for x, y, w, h in found:
                # Convert the enlarged-frame coordinates back to original.
                ox = int(round(x / scale))
                oy = int(round(y / scale))
                ow = int(round(w / scale))
                oh = int(round(h / scale))
                boxes.append((ox, oy, ow, oh))

        return boxes

    def detect(self, frame: np.ndarray) -> List[BBox]:
        """Detect faces and return ``(x, y, width, height)`` in frame pixels."""
        if not self._cascades or frame is None or getattr(frame, "size", 0) == 0:
            return []

        try:
            height, width = frame.shape[:2]
            # Upscaling is important for CCTV faces that occupy only a small
            # fraction of a 720p/1080p frame. Avoid excessive CPU cost on 4K.
            max_dimension = max(height, width)
            scale = 1.8 if max_dimension <= 1280 else 1.35
            scale = min(scale, 2.0)

            gray = self._prepare(frame, scale)
            boxes = self._detect_pass(gray, scale, profile=False)

            # Profile detection is deliberately secondary. It improves recall
            # for side-facing subjects without making frontal detection overly
            # permissive.
            profile_gray = cv2.flip(gray, 1)
            profile_boxes = self._detect_pass(profile_gray, scale, profile=True)
            for x, y, w, h in profile_boxes:
                x = int(gray.shape[1] - (x + w))
                boxes.append((x, y, w, h))

            # A second, unscaled pass is useful for very large close-up faces
            # and avoids relying entirely on the enlarged image.
            if not boxes:
                original_gray = self._prepare(frame, 1.0)
                boxes = self._detect_pass(original_gray, 1.0, profile=False)

            valid: List[BBox] = []
            for x, y, w, h in boxes:
                x = max(0, min(x, width - 1))
                y = max(0, min(y, height - 1))
                w = min(w, width - x)
                h = min(h, height - y)
                if w >= self._min_face_size and h >= self._min_face_size:
                    valid.append((x, y, w, h))

            return self._deduplicate(valid)
        except Exception as exc:
            log.warning("Face detection failed on frame: %s", exc)
            return []
