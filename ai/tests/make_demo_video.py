"""
ai/tests/make_demo_video.py
Generates a short synthetic video that exercises the pipeline without
needing a real camera or real footage: a car-shaped rectangle with a
readable plate on it drives across the frame and through the fence zone
defined in the README's example FENCE_ZONE.

This does NOT replace real footage for a real demo — a plain colored
rectangle won't trigger YOLO's actual "car" class (YOLO needs real visual
features, not a shape). This is meant for testing the plumbing (video
looping, frame reading, the fence-crossing logic) end to end without a
camera attached. For an actual demo, use a real short traffic/surveillance
clip as --source instead.

Run: python -m ai.tests.make_demo_video [output_path]
"""
import sys

import cv2
import numpy as np

DEFAULT_OUTPUT = "demo_video.mp4"
WIDTH, HEIGHT = 640, 480
FPS = 20
DURATION_SECONDS = 6


def make_demo_video(path: str = DEFAULT_OUTPUT):
    fourcc = cv2.VideoWriter_fourcc(*"mp4v")
    writer = cv2.VideoWriter(path, fourcc, FPS, (WIDTH, HEIGHT))

    total_frames = FPS * DURATION_SECONDS
    car_w, car_h = 120, 70

    for i in range(total_frames):
        frame = np.full((HEIGHT, WIDTH, 3), 40, dtype=np.uint8)  # dark background

        # A visible reference rectangle showing where the example fence
        # zone from the README (FENCE_ZONE=[[100,100],[400,100],[400,400],[100,400]])
        # sits, so it's obvious in the video when the "car" crosses it.
        cv2.rectangle(frame, (100, 100), (400, 400), (60, 60, 200), 2)
        cv2.putText(frame, "FENCE ZONE", (105, 95), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (60, 60, 200), 1)

        # "Car" — a rectangle sliding left to right through the zone, with
        # a readable plate drawn on its lower edge.
        progress = i / total_frames
        car_x = int(-car_w + progress * (WIDTH + car_w * 2))
        car_y = 220
        cv2.rectangle(frame, (car_x, car_y), (car_x + car_w, car_y + car_h), (200, 200, 200), -1)
        cv2.rectangle(frame, (car_x, car_y), (car_x + car_w, car_y + car_h), (0, 0, 0), 2)

        plate_x, plate_y = car_x + 15, car_y + car_h - 25
        cv2.rectangle(frame, (plate_x, plate_y), (plate_x + 90, plate_y + 20), (255, 255, 255), -1)
        cv2.rectangle(frame, (plate_x, plate_y), (plate_x + 90, plate_y + 20), (0, 0, 0), 1)
        cv2.putText(frame, "DL7CAF1234", (plate_x + 3, plate_y + 15), cv2.FONT_HERSHEY_SIMPLEX, 0.4, (0, 0, 0), 1)

        writer.write(frame)

    writer.release()
    print(f"Wrote {total_frames} frames ({DURATION_SECONDS}s @ {FPS}fps) to {path}")


if __name__ == "__main__":
    out = sys.argv[1] if len(sys.argv) > 1 else DEFAULT_OUTPUT
    make_demo_video(out)
