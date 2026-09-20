"""
ai/tracking/tracker.py
Minimal centroid-distance tracker: assigns a stable ID to each detection by
matching it to the closest tracked object from the previous frame (within
a distance threshold). No ML involved — this is the standard cheap
approach before reaching for something like ByteTrack/DeepSORT.
"""
import math
from typing import Dict, List, Tuple

from ai.utils.logger import get_logger

log = get_logger(__name__)

BBox = Tuple[float, float, float, float]  # x1, y1, x2, y2


def _centroid(bbox: BBox) -> Tuple[float, float]:
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def _distance(a: Tuple[float, float], b: Tuple[float, float]) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


class CentroidTracker:
    def __init__(self, max_distance: float = 75.0, max_missed_frames: int = 15):
        self._next_id = 1
        self._objects: Dict[int, Tuple[float, float]] = {}   # id -> centroid
        self._missed: Dict[int, int] = {}                    # id -> frames missed
        self._max_distance = max_distance
        self._max_missed_frames = max_missed_frames

    def update(self, bboxes: List[BBox]) -> Dict[int, BBox]:
        """
        Takes this frame's detected bounding boxes, returns {track_id: bbox}
        with IDs kept stable across calls where possible.
        """
        centroids = [_centroid(b) for b in bboxes]

        if not self._objects:
            result = {}
            for c, b in zip(centroids, bboxes):
                self._objects[self._next_id] = c
                self._missed[self._next_id] = 0
                result[self._next_id] = b
                self._next_id += 1
            return result

        unmatched_detections = set(range(len(centroids)))
        unmatched_ids = set(self._objects.keys())
        result: Dict[int, BBox] = {}

        # Greedy nearest-neighbor matching — fine for a prototype with a
        # handful of objects; swap for the Hungarian algorithm if this ever
        # needs to handle dozens of simultaneous tracks accurately.
        pairs = []
        for tid in unmatched_ids:
            for di in unmatched_detections:
                d = _distance(self._objects[tid], centroids[di])
                if d <= self._max_distance:
                    pairs.append((d, tid, di))
        pairs.sort(key=lambda p: p[0])

        used_ids, used_dets = set(), set()
        for d, tid, di in pairs:
            if tid in used_ids or di in used_dets:
                continue
            self._objects[tid] = centroids[di]
            self._missed[tid] = 0
            result[tid] = bboxes[di]
            used_ids.add(tid)
            used_dets.add(di)

        unmatched_ids -= used_ids
        unmatched_detections -= used_dets

        # New detections become new tracks.
        for di in unmatched_detections:
            tid = self._next_id
            self._next_id += 1
            self._objects[tid] = centroids[di]
            self._missed[tid] = 0
            result[tid] = bboxes[di]

        # Tracks with no match this frame — age them out after too many misses.
        for tid in unmatched_ids:
            self._missed[tid] = self._missed.get(tid, 0) + 1
            if self._missed[tid] > self._max_missed_frames:
                del self._objects[tid]
                del self._missed[tid]

        return result
