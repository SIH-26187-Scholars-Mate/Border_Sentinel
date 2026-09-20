"""
ai/anpr/plate_detector.py
Locates candidate license-plate regions using a classic contour/edge
heuristic (no trained model needed for a prototype). Plates are found by
looking for high-contrast rectangular regions with a plate-like aspect
ratio. This is deliberately simple — swap for a trained plate detector
if false-positive rate becomes a problem on real footage.
"""
from typing import List, Tuple

import cv2
import numpy as np

from ai.utils.logger import get_logger

log = get_logger(__name__)

BBox = Tuple[int, int, int, int]  # x, y, w, h

# Real plates are wider than tall; this range is deliberately generous
# for a first-pass heuristic.
_MIN_ASPECT, _MAX_ASPECT = 2.0, 6.0
_MIN_AREA = 500


class PlateDetector:
    def detect(self, frame: np.ndarray) -> List[BBox]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.bilateralFilter(gray, 11, 17, 17)
        edges = cv2.Canny(blurred, 30, 200)

        contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)

        candidates = []
        for c in contours:
            x, y, w, h = cv2.boundingRect(c)
            if h == 0:
                continue
            area = w * h
            aspect = w / h
            if area >= _MIN_AREA and _MIN_ASPECT <= aspect <= _MAX_ASPECT:
                candidates.append((x, y, w, h))

        return candidates

    def crop(self, frame: np.ndarray, bbox: BBox) -> np.ndarray:
        x, y, w, h = bbox
        return frame[y : y + h, x : x + w]
