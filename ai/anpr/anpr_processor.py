"""
ai/anpr/anpr_processor.py
Ties plate_detector.py + ocr.py together into one function the pipeline
can call for a single vehicle detection: given the frame and that
vehicle's bounding box, find its plate (if any) and read it.

This is the piece that was missing before — plate_detector.py and ocr.py
existed but nothing called them from the actual detection pipeline.
"""
from typing import Optional, Tuple

import numpy as np

from ai.anpr.ocr import read_plate
from ai.anpr.plate_detector import PlateDetector
from ai.utils.logger import get_logger

log = get_logger(__name__)

BBox = Tuple[float, float, float, float]  # x1, y1, x2, y2 (vehicle box, from the detector)

# A real plate reads at least this many characters after cleanup — OCR
# noise on a bad crop tends to produce very short or empty strings, so this
# is a cheap way to reject obvious garbage before reporting it as a find.
_MIN_PLATE_LENGTH = 4


class ANPRProcessor:
    def __init__(self):
        self._plate_detector = PlateDetector()

    def read_plate_for_vehicle(self, frame: np.ndarray, vehicle_bbox: BBox) -> Optional[str]:
        """
        Crops the vehicle region out of the frame, searches THAT crop for a
        plate-shaped candidate (much more reliable than scanning the whole
        frame — fewer false-positive rectangles to sort through), OCRs the
        best candidate, and returns the cleaned text, or None if nothing
        plate-like/readable was found.
        """
        h, w = frame.shape[:2]
        x1, y1, x2, y2 = vehicle_bbox
        # Clamp to frame bounds — detector boxes can slightly overshoot the
        # edges of the image.
        x1, y1 = max(0, int(x1)), max(0, int(y1))
        x2, y2 = min(w, int(x2)), min(h, int(y2))
        if x2 <= x1 or y2 <= y1:
            return None

        vehicle_crop = frame[y1:y2, x1:x2]
        candidates = self._plate_detector.detect(vehicle_crop)
        if not candidates:
            return None

        # Plates sit in the lower half of a vehicle in most footage angles,
        # and are the widest plate-shaped candidate found — use that as the
        # tiebreaker between multiple contour matches.
        best = max(candidates, key=lambda b: b[2] * b[3])
        plate_crop = self._plate_detector.crop(vehicle_crop, best)

        try:
            text = read_plate(plate_crop)
        except RuntimeError as exc:
            # Tesseract not installed, or OCR genuinely failed — log once,
            # don't crash the pipeline over a missing system dependency.
            log.warning("OCR failed: %s", exc)
            return None

        if len(text) < _MIN_PLATE_LENGTH:
            return None
        return text
