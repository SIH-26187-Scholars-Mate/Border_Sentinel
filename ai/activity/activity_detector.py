"""
ai/activity/activity_detector.py
Heuristic activity detection based on a tracked object's centroid history —
no action-recognition model needed for a prototype. Flags two patterns:

  - "loitering":       centroid barely moves over a sustained window
  - "rapid_movement":  centroid moves further, faster, than expected
                        between consecutive frames

Feed it the same {track_id: bbox} dict the tracker/fence use each frame.
"""
import math
from collections import defaultdict, deque
from typing import Deque, Dict, List, Tuple

from ai.utils.logger import get_logger

log = get_logger(__name__)

BBox = Tuple[float, float, float, float]
Point = Tuple[float, float]


def _centroid(bbox: BBox) -> Point:
    x1, y1, x2, y2 = bbox
    return ((x1 + x2) / 2, (y1 + y2) / 2)


def _distance(a: Point, b: Point) -> float:
    return math.hypot(a[0] - b[0], a[1] - b[1])


class ActivityDetector:
    def __init__(
        self,
        loiter_window_frames: int = 90,     # ~3s at 30fps
        loiter_max_movement: float = 40.0,  # total centroid drift allowed to still count as "loitering"
        rapid_movement_threshold: float = 60.0,  # pixels moved in one frame
        event_cooldown_frames: int = 30,          # avoid one alert per frame
    ):
        self._history: Dict[int, Deque[Point]] = defaultdict(
            lambda: deque(maxlen=loiter_window_frames)
        )
        self._loiter_window = loiter_window_frames
        self._loiter_max_movement = loiter_max_movement
        self._rapid_threshold = rapid_movement_threshold
        self._cooldown = max(0, event_cooldown_frames)
        self._last_emitted: Dict[Tuple[int, str], int] = {}
        self._frame = 0

    def update(self, tracked: Dict[int, BBox], class_by_id: Dict[int, str] | None = None) -> List[dict]:
        """Returns a list of {track_id, activity} events detected this frame."""
        self._frame += 1
        events = []
        class_by_id = class_by_id or {}

        for track_id, bbox in tracked.items():
            c = _centroid(bbox)
            history = self._history[track_id]

            if history:
                step = _distance(history[-1], c)
                if step >= self._rapid_threshold and self._can_emit(track_id, "rapid_movement"):
                    events.append({"track_id": track_id, "activity": "rapid_movement", "magnitude": step})
                    self._mark_emitted(track_id, "rapid_movement")
                if step > 15 and c[0] < history[-1][0] and self._can_emit(track_id, "wrong_direction"):
                    events.append({"track_id": track_id, "activity": "wrong_direction", "magnitude": step})
                    self._mark_emitted(track_id, "wrong_direction")

            history.append(c)

            if len(history) == self._loiter_window:
                total_drift = _distance(history[0], history[-1])
                # Check and mark the SAME key (the actual activity name,
                # which differs for vehicles vs. people) — checking
                # "loitering" but marking "vehicle_loitering" meant the
                # cooldown never matched for vehicles, so this fired every
                # single frame instead of once per loitering spell.
                activity = "vehicle_loitering" if class_by_id.get(track_id) in {"car","truck","bus","motorcycle"} else "loitering"
                if total_drift <= self._loiter_max_movement and self._can_emit(track_id, activity):
                    events.append({"track_id": track_id, "activity": activity, "magnitude": total_drift})
                    self._mark_emitted(track_id, activity)

        # Drop stale cooldown entries for tracks that are no longer present.
        active_ids = set(tracked)
        self._history = defaultdict(lambda: deque(maxlen=self._loiter_window),
                                    {tid: hist for tid, hist in self._history.items() if tid in active_ids})
        self._last_emitted = {key: frame for key, frame in self._last_emitted.items()
                              if key[0] in active_ids and self._frame - frame <= self._cooldown * 2}
        return events

    def _can_emit(self, track_id: int, activity: str) -> bool:
        last = self._last_emitted.get((track_id, activity))
        return last is None or self._frame - last > self._cooldown

    def _mark_emitted(self, track_id: int, activity: str) -> None:
        self._last_emitted[(track_id, activity)] = self._frame
