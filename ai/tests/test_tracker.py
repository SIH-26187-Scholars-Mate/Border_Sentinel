from ai.tracking.tracker import CentroidTracker


def test_tracks_stay_stable_across_frames():
    tracker = CentroidTracker(max_distance=50)

    # Frame 1: one object at (100,100)-(150,150)
    result1 = tracker.update([(100, 100, 150, 150)])
    assert len(result1) == 1
    tid = list(result1.keys())[0]

    # Frame 2: same object moved slightly — should keep the same ID
    result2 = tracker.update([(105, 105, 155, 155)])
    assert list(result2.keys()) == [tid]

    # Frame 3: moved further but still within max_distance
    result3 = tracker.update([(115, 115, 165, 165)])
    assert list(result3.keys()) == [tid]


def test_new_object_gets_new_id():
    tracker = CentroidTracker(max_distance=50)
    r1 = tracker.update([(0, 0, 50, 50)])
    id1 = list(r1.keys())[0]

    # A second, far-away object should NOT reuse the same ID
    r2 = tracker.update([(0, 0, 50, 50), (1000, 1000, 1050, 1050)])
    assert id1 in r2
    assert len(r2) == 2


def test_object_dropped_after_missing_too_long():
    tracker = CentroidTracker(max_distance=50, max_missed_frames=2)
    tracker.update([(0, 0, 50, 50)])

    # object disappears for more frames than max_missed_frames
    tracker.update([])
    tracker.update([])
    result = tracker.update([])
    assert len(tracker._objects) == 0
