"""
ai/face/face_detector.py
Face detection using OpenCV's bundled Haar cascade — no extra model file
to manage, it ships inside opencv-python itself. Swap for a DNN-based
detector later if accuracy on angled/partial faces becomes a problem.
"""
from typing import List, Tuple

import cv2
import numpy as np

from ai.utils.logger import get_logger

log = get_logger(__name__)

BBox = Tuple[int, int, int, int]  # x, y, w, h


class FaceDetector:
    def __init__(self):
        cascade_path = getattr(cv2, "data", None)
        if cascade_path and hasattr(cascade_path, "haarcascades") and hasattr(cv2, "CascadeClassifier"):
            xml_path = cascade_path.haarcascades + "haarcascade_frontalface_default.xml"
            self._cascade = cv2.CascadeClassifier(xml_path)
            if self._cascade.empty():
                self._cascade = None
                log.warning("Could not load face cascade from %s", xml_path)
            else:
                log.info("Loaded face cascade from %s", xml_path)
        else:
            self._cascade = None
            log.warning("cv2.CascadeClassifier or haarcascades data unavailable")

    def detect(self, frame: np.ndarray) -> List[BBox]:
        if self._cascade is None:
            return []
        try:
            gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
            faces = self._cascade.detectMultiScale(
                gray, scaleFactor=1.1, minNeighbors=5, minSize=(30, 30)
            )
            return [tuple(f) for f in faces]
        except Exception as e:
            log.warning("Face detection failed on frame: %s", e)
            return []
