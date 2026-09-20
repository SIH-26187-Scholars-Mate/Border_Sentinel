from ai.activity.activity_detector import ActivityDetector


def test_rapid_movement_detected():
    detector = ActivityDetector(rapid_movement_threshold=50)
    detector.update({1: (0, 0, 20, 20)})
    events = detector.update({1: (200, 200, 220, 220)})  # big jump
    assert any(e["activity"] == "rapid_movement" for e in events)


def test_small_movement_not_flagged_as_rapid():
    detector = ActivityDetector(rapid_movement_threshold=50)
    detector.update({1: (0, 0, 20, 20)})
    events = detector.update({1: (5, 5, 25, 25)})  # tiny move
    assert not any(e["activity"] == "rapid_movement" for e in events)


def test_loitering_detected_after_window():
    detector = ActivityDetector(loiter_window_frames=5, loiter_max_movement=10)
    events = []
    for _ in range(5):
        events = detector.update({1: (100, 100, 120, 120)})  # barely moves
    assert any(e["activity"] == "loitering" for e in events)
