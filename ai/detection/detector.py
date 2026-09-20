"""
ai/detection/detector.py
General object detection using a pretrained YOLOv8 model (ultralytics).
Model weights are NOT shipped in this repo — ultralytics downloads
yolov8n.pt automatically on first use (cached under ~/.cache after that).
"""
from dataclasses import dataclass
from typing import List

import numpy as np

from ai.utils.config import get_settings
from ai.utils.logger import get_logger

log = get_logger(__name__)


@dataclass
class Detection:
    class_name: str
    confidence: float
    bbox: tuple  # (x1, y1, x2, y2) in pixel coordinates


class Detector:
    def __init__(self, model_path: str = "yolov8n.pt"):
        from ultralytics import YOLO  # imported lazily so importing this
        # module doesn't require torch unless you actually build a Detector

        self._model = YOLO(model_path)
        self._threshold = get_settings().confidence_threshold
        log.info("Loaded detector model: %s (threshold=%.2f)", model_path, self._threshold)

    def detect(self, frame: np.ndarray) -> List[Detection]:
        results = self._model(frame, verbose=False)[0]
        detections = []
        for box in results.boxes:
            conf = float(box.conf[0])
            if conf < self._threshold:
                continue
            cls_id = int(box.cls[0])
            name = results.names[cls_id]
            x1, y1, x2, y2 = box.xyxy[0].tolist()
            detections.append(Detection(name, conf, (x1, y1, x2, y2)))
        return detections
