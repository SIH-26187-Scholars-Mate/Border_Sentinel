from ai.intrusion.virtual_fence import VirtualFence, polygon_for_frame

ZONE = [(100, 100), (400, 100), (400, 400), (100, 400)]


def test_object_outside_zone_does_not_trigger():
    fence = VirtualFence(ZONE)
    entered = fence.check({1: (0, 0, 20, 20)})  # centroid (10,10) — outside
    assert entered == []


def test_object_entering_zone_triggers_once():
    fence = VirtualFence(ZONE)
    # Frame 1: outside
    assert fence.check({1: (0, 0, 20, 20)}) == []
    # Frame 2: now inside the zone
    entered = fence.check({1: (240, 240, 260, 260)})
    assert entered == [1]
    # Frame 3: still inside — must NOT fire again
    entered_again = fence.check({1: (245, 245, 265, 265)})
    assert entered_again == []


def test_object_leaving_and_reentering_fires_twice():
    fence = VirtualFence(ZONE)
    fence.check({1: (0, 0, 20, 20)})                    # outside
    assert fence.check({1: (240, 240, 260, 260)}) == [1]  # enters -> fires
    fence.check({1: (0, 0, 20, 20)})                     # leaves
    assert fence.check({1: (240, 240, 260, 260)}) == [1]  # re-enters -> fires again


def test_normalized_zone_scales_to_laptop_webcam():
    points = [(0.25, 0.25), (0.75, 0.25), (0.75, 0.75), (0.25, 0.75)]
    assert polygon_for_frame(points, 640, 480) == [
        (160.0, 120.0), (480.0, 120.0), (480.0, 360.0), (160.0, 360.0)
    ]


def test_normalized_zone_scales_to_portrait_mobile_frame():
    points = [(0.25, 0.2), (0.75, 0.2), (0.75, 0.8), (0.25, 0.8)]
    assert polygon_for_frame(points, 720, 1280) == [
        (180.0, 256.0), (540.0, 256.0), (540.0, 1024.0), (180.0, 1024.0)
    ]


def test_old_1280x720_zone_remains_backward_compatible():
    points = [(320, 180), (960, 180), (960, 540), (320, 540)]
    assert polygon_for_frame(points, 640, 480) == [
        (160.0, 120.0), (480.0, 120.0), (480.0, 360.0), (160.0, 360.0)
    ]
