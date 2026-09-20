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


def _walk(detector, xs, y=100, size=20):
    events = []
    for x in xs:
        events += detector.update({1: (x, y, x + size, y + size)})
    return events


def test_counter_flow_flagged_when_moving_against_expected_direction():
    detector = ActivityDetector(flow_direction="right")
    events = _walk(detector, range(400, 300, -10))   # steadily moving LEFT, 100 px total
    assert any(e["activity"] == "counter_flow" for e in events)


def test_moving_with_the_flow_is_not_flagged():
    detector = ActivityDetector(flow_direction="right")
    events = _walk(detector, range(100, 200, 10))    # steadily moving RIGHT
    assert not any(e["activity"] == "counter_flow" for e in events)


def test_single_frame_jitter_is_not_counter_flow():
    detector = ActivityDetector(flow_direction="right")
    # Mostly rightward with one 20 px leftward wobble: net trend is with the flow.
    events = _walk(detector, [100, 110, 120, 100, 130, 140, 150, 160, 170, 180])
    assert not any(e["activity"] == "counter_flow" for e in events)


def test_flow_direction_none_disables_the_check():
    detector = ActivityDetector(flow_direction="none")
    events = _walk(detector, range(400, 300, -10))
    assert not any(e["activity"] == "counter_flow" for e in events)


def test_vertical_flow_direction_is_respected():
    detector = ActivityDetector(flow_direction="down")
    events = []
    for y in range(300, 200, -10):                    # moving UP, against "down"
        events += detector.update({1: (100, y, 120, y + 20)})
    assert any(e["activity"] == "counter_flow" for e in events)


def test_labels_are_human_readable_and_old_key_still_maps():
    from ai.activity.activity_detector import activity_description, activity_label
    assert activity_label("counter_flow") == "Counter-flow movement"
    assert activity_label("wrong_direction") == "Counter-flow movement"
    assert "expected direction" in activity_description("counter_flow")
