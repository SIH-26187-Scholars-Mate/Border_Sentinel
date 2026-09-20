"""Vehicle-crop -> dedicated plate detector -> OCR."""
from __future__ import annotations
from typing import Dict, Optional, Tuple
import numpy as np
from ai.anpr.ocr import read_plate
from ai.anpr.plate_detector import PlateDetector
from ai.utils.logger import get_logger

log = get_logger(__name__)
BBox = Tuple[float, float, float, float]
_MIN_PLATE_LENGTH = 4


class ANPRProcessor:
    def __init__(self, scan_interval_frames: Optional[int] = None, max_candidates: int = 3):
        self._plate_detector = PlateDetector()
        # Without the trained YOLO plate model the detector falls back to a
        # contour heuristic that returns many false candidates, and every
        # candidate costs a Tesseract call (100-500 ms). Scan less often then.
        if scan_interval_frames is None:
            scan_interval_frames = 3 if self._plate_detector.using_yolo else 8
        self._scan_interval_frames = max(1, int(scan_interval_frames))
        self._max_candidates = max(1, int(max_candidates))
        self._last_scan: Dict[int, int] = {}

    @property
    def using_yolo_plate_detector(self) -> bool:
        return self._plate_detector.using_yolo

    def _should_scan(self, track_id: Optional[int], frame_index: Optional[int]) -> bool:
        if track_id is None or frame_index is None:
            return True
        last = self._last_scan.get(track_id)
        if last is not None and frame_index - last < self._scan_interval_frames:
            return False
        self._last_scan[track_id] = frame_index
        return True

    def read_plate_for_vehicle(self, frame: np.ndarray, vehicle_bbox: BBox,
                               track_id: Optional[int] = None,
                               frame_index: Optional[int] = None) -> Optional[str]:
        if not self._should_scan(track_id, frame_index):
            return None
        height, width = frame.shape[:2]
        x1, y1, x2, y2 = vehicle_bbox
        x1, y1 = max(0, int(x1)), max(0, int(y1))
        x2, y2 = min(width, int(x2)), min(height, int(y2))
        if x2 <= x1 or y2 <= y1:
            return None
        vehicle_crop = frame[y1:y2, x1:x2]
        if vehicle_crop.size == 0:
            return None
        candidates = self._plate_detector.detect(vehicle_crop)
        if not candidates:
            return None
        for bbox in candidates[:self._max_candidates]:
            plate_crop = self._plate_detector.crop(vehicle_crop, bbox)
            if plate_crop.size == 0:
                continue
            try:
                text = read_plate(plate_crop)
            except RuntimeError as exc:
                log.warning("OCR failed: %s", exc)
                return None
            if len(text) >= _MIN_PLATE_LENGTH:
                return text
        return None
