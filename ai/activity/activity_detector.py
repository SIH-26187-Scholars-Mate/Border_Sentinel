"""
ai/activity/activity_detector.py
Heuristic activity detection based on a tracked object's centroid history —
no action-recognition model needed for a prototype. Flags these patterns:

  - "loitering":       centroid barely moves over a sustained window
  - "rapid_movement":  centroid moves further, faster, than expected
                        between consecutive frames
  - "counter_flow":    sustained movement AGAINST the camera's expected
                        direction of travel (see FLOW_DIRECTION below)

Counter-flow, in plain words: each camera has an expected direction of
travel (default: left -> right, set with FLOW_DIRECTION=right|left|up|down,
or FLOW_DIRECTION=none to switch the check off). An object is flagged only
when its centroid has moved at least `counter_flow_min_px` pixels the
opposite way over the last `counter_flow_window` frames — a sustained
trend, not a single-frame jitter of the bounding box.

Feed it the same {track_id: bbox} dict the tracker/fence use each frame.
"""
import math
from collections import defaultdict, deque
from typing import Deque, Dict, List, Tuple

from ai.utils.config import setting
from ai.utils.logger import get_logger

log = get_logger(__name__)

BBox = Tuple[float, float, float, float]
Point = Tuple[float, float]


# Human-readable names for the internal activity keys. Use these anywhere an
# operator or a report reader sees an activity, so the wording is consistent
# and explainable. "wrong_direction" is the old key for counter_flow and is
# kept so previously saved alerts/reports still display sensibly.
ACTIVITY_LABELS = {
    "counter_flow": "Counter-flow movement",
    "wrong_direction": "Counter-flow movement",
    "rapid_movement": "Rapid movement",
    "loitering": "Loitering",
    "vehicle_loitering": "Vehicle loitering",
}

ACTIVITY_EXPLANATIONS = {
    "counter_flow": "moving against the expected direction of travel",
    "wrong_direction": "moving against the expected direction of travel",
    "rapid_movement": "moved much farther between frames than normal",
    "loitering": "stayed almost stationary for an extended period",
    "vehicle_loitering": "vehicle stayed almost stationary for an extended period",
}

# unit vectors in image coordinates (x grows right, y grows DOWN)
_FLOW_VECTORS = {"right": (1.0, 0.0), "left": (-1.0, 0.0), "down": (0.0, 1.0), "up": (0.0, -1.0)}


def activity_label(activity: str) -> str:
    return ACTIVITY_LABELS.get(activity, str(activity).replace("_", " ").capitalize())


def activity_description(activity: str) -> str:
    """e.g. 'Counter-flow movement (moving against the expected direction of travel)'."""
    label = activity_label(activity)
    why = ACTIVITY_EXPLANATIONS.get(activity)
    return f"{label} ({why})" if why else label


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
        flow_direction: str | None = None,        # expected direction of travel; None -> FLOW_DIRECTION setting (default "right")
        counter_flow_window: int = 8,             # frames over which net movement is measured
        counter_flow_min_px: float = 40.0,        # net pixels moved against the flow to count
    ):
        direction = str(flow_direction if flow_direction is not None
                        else setting("flow_direction", "right")).strip().lower()
        # Anything that isn't a known direction ("none", "off", "") disables the check.
        self._flow = _FLOW_VECTORS.get(direction)
        self._counter_flow_window = max(2, int(counter_flow_window))
        self._counter_flow_min_px = float(counter_flow_min_px)
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
                if self._flow is not None and len(history) >= self._counter_flow_window:
                    # Net movement over the window, projected on the expected
                    # direction of travel; negative = going the opposite way.
                    ref = history[-self._counter_flow_window]
                    along = (c[0] - ref[0]) * self._flow[0] + (c[1] - ref[1]) * self._flow[1]
                    if along <= -self._counter_flow_min_px and self._can_emit(track_id, "counter_flow"):
                        events.append({"track_id": track_id, "activity": "counter_flow", "magnitude": abs(along)})
                        self._mark_emitted(track_id, "counter_flow")

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
