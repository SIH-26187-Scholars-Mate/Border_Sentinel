"""Dedicated Indian YOLOv8 license-plate detector for Border Sentinel.

Runs on CPU by design. Falls back to the original contour detector if the
dedicated model is unavailable or fails, so the pipeline remains runnable.
"""
from __future__ import annotations
import os
from pathlib import Path
from typing import List, Optional, Tuple
import cv2
import numpy as np
from ai.utils.logger import get_logger

log = get_logger(__name__)
BBox = Tuple[int, int, int, int]
_DEFAULT_MODEL = Path(__file__).resolve().parent / "models" / "Lavanya_NamePlateModel.pt"
_DEFAULT_CONF = 0.25
_MIN_MODEL_SIZE = 1024 * 1024
_MIN_ASPECT, _MAX_ASPECT, _MIN_AREA = 2.0, 6.0, 500


class PlateDetector:
    def __init__(self, model_path: Optional[str] = None,
                 confidence: Optional[float] = None, device: str = "cpu"):
        configured = os.getenv("ANPR_PLATE_MODEL_PATH")
        self._model_path = Path(model_path or configured or _DEFAULT_MODEL).expanduser()
        self._confidence = float(confidence if confidence is not None
                                 else os.getenv("ANPR_PLATE_CONF", _DEFAULT_CONF))
        self._device = device
        self._model = None
        self._using_yolo = False
        self._load_yolo_model()

    @property
    def using_yolo(self) -> bool:
        return self._using_yolo

    def _load_yolo_model(self) -> None:
        if not self._model_path.exists():
            log.warning(
                "Indian YOLO plate model not found at %s; using contour fallback. "
                "Run 'python -m ai.anpr.download_plate_model' first.",
                self._model_path,
            )
            return
        try:
            if self._model_path.stat().st_size < _MIN_MODEL_SIZE:
                log.warning("Plate model at %s is unexpectedly small; using contour fallback.",
                            self._model_path)
                return
        except OSError as exc:
            log.warning("Could not inspect plate model: %s", exc)
            return
        try:
            from ultralytics import YOLO
            self._model = YOLO(str(self._model_path))
            self._using_yolo = True
            log.info("Loaded Indian YOLOv8 plate detector from %s (CPU, conf=%.2f)",
                     self._model_path, self._confidence)
        except Exception as exc:
            log.warning("Could not load Indian YOLO plate model: %s; using contour fallback.", exc)

    def _detect_yolo(self, frame: np.ndarray) -> List[BBox]:
        try:
            result = self._model.predict(
                source=frame, conf=self._confidence, imgsz=640,
                device=self._device, verbose=False
            )[0]
        except Exception as exc:
            log.warning("Indian YOLO plate inference failed: %s", exc)
            return []
        if result.boxes is None:
            return []
        height, width = frame.shape[:2]
        candidates = []
        for box in result.boxes:
            try:
                confidence = float(box.conf[0])
                x1, y1, x2, y2 = [int(v) for v in box.xyxy[0].tolist()]
            except (IndexError, TypeError, ValueError):
                continue
            x1, y1 = max(0, min(x1, width - 1)), max(0, min(y1, height - 1))
            x2, y2 = max(0, min(x2, width)), max(0, min(y2, height))
            if x2 > x1 and y2 > y1:
                candidates.append(((x1, y1, x2-x1, y2-y1), confidence))
        candidates.sort(key=lambda item: (item[1], item[0][2] * item[0][3]), reverse=True)
        return [bbox for bbox, _ in candidates]

    @staticmethod
    def _detect_contours(frame: np.ndarray) -> List[BBox]:
        gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
        blurred = cv2.bilateralFilter(gray, 11, 17, 17)
        edges = cv2.Canny(blurred, 30, 200)
        contours, _ = cv2.findContours(edges, cv2.RETR_LIST, cv2.CHAIN_APPROX_SIMPLE)
        candidates = []
        for contour in contours:
            x, y, w, h = cv2.boundingRect(contour)
            if h == 0:
                continue
            area, aspect = w * h, w / h
            if area >= _MIN_AREA and _MIN_ASPECT <= aspect <= _MAX_ASPECT:
                candidates.append((x, y, w, h))
        # Preserve the previous fallback behavior: choose the largest
        # plate-shaped contour first when the trained model is unavailable.
        candidates.sort(key=lambda b: b[2] * b[3], reverse=True)
        return candidates

    def detect(self, frame: np.ndarray) -> List[BBox]:
        if frame is None or getattr(frame, "size", 0) == 0:
            return []
        if self._using_yolo:
            candidates = self._detect_yolo(frame)
            if candidates:
                return candidates
        return self._detect_contours(frame)

    @staticmethod
    def crop(frame: np.ndarray, bbox: BBox) -> np.ndarray:
        x, y, w, h = bbox
        return frame[y:y+h, x:x+w]
