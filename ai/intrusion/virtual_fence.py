"""
ai/intrusion/virtual_fence.py
Defines a polygon "restricted zone" and detects when a tracked object's
centroid crosses into it — debounced so a single crossing fires exactly
one event, not one per frame the object stays inside the zone.
"""
from typing import Dict, List, Set, Tuple

import cv2
import numpy as np

from ai.utils.logger import get_logger

log = get_logger(__name__)

Point = Tuple[float, float]
BBox = Tuple[float, float, float, float]

# The original zone editor stored points in a fixed 1280x720 coordinate
# system. New zones are stored as normalized coordinates (0..1), so the same
# fence can be used safely with 16:9, 4:3, portrait/mobile, and HD sources.
LEGACY_ZONE_WIDTH = 1280.0
LEGACY_ZONE_HEIGHT = 720.0


def polygon_for_frame(points: List[Point], frame_width: int, frame_height: int) -> List[Point]:
    """Convert stored fence coordinates to the current camera frame.

    New zones use normalized coordinates:
        (0..1, 0..1) -> current frame pixels.

    Older Border Sentinel zones used 1280x720 pixel coordinates. They are
    scaled to the actual frame for backwards compatibility.
    """
    if not points:
        return []

    # A normalized zone has every coordinate within the 0..1 range.
    normalized = all(0.0 <= float(x) <= 1.0 and 0.0 <= float(y) <= 1.0
                     for x, y in points)

    if normalized:
        return [
            (float(x) * frame_width, float(y) * frame_height)
            for x, y in points
        ]

    # Backwards compatibility for zones saved by the old 1280x720 editor.
    sx = frame_width / LEGACY_ZONE_WIDTH
    sy = frame_height / LEGACY_ZONE_HEIGHT
    return [(float(x) * sx, float(y) * sy) for x, y in points]


def _centroid(bbox: BBox) -> Point:
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2, (y1 + y2) / 2)


class VirtualFence:
    def __init__(self, polygon: List[Point]):
        if len(polygon) < 3:
            raise ValueError("A fence zone needs at least 3 points")
        self._polygon = np.array(polygon, dtype=np.float32)
        self._inside_ids: Set[int] = set()  # track IDs currently inside the zone

    def is_inside(self, point: Point) -> bool:
        result = cv2.pointPolygonTest(self._polygon, point, False)
        return result >= 0

    def check(self, tracked: Dict[int, BBox]) -> List[int]:
        """
        Given this frame's {track_id: bbox}, returns the list of track IDs
        that just crossed INTO the zone this frame (i.e. weren't inside last
        frame, are inside now). Only these should trigger a new alert.
        """
        currently_inside = set()
        newly_entered = []

        for track_id, bbox in tracked.items():
            c = _centroid(bbox)
            if self.is_inside(c):
                currently_inside.add(track_id)
                if track_id not in self._inside_ids:
                    newly_entered.append(track_id)

        self._inside_ids = currently_inside
        if newly_entered:
            log.info("Zone crossed by track IDs: %s", newly_entered)
        return newly_entered
