# Border Sentinel — AI Module

## Setup
This module shares one venv with `backend/` at the project root — see the
top-level `README.md`'s "Set up the Python environment" step (run
`../setup.sh` or `../setup_windows.bat` once, from the project root, if you
haven't). From here, just activate it:
```bash
source ../.venv/bin/activate    # ..\.venv\Scripts\activate on Windows
```
Requires the system Tesseract binary for `anpr/ocr.py` to work:
```
sudo apt install tesseract-ocr      # Ubuntu/Debian
brew install tesseract              # macOS
```
Create a `.env` (see `.env.example` if present, or use this):
```
BACKEND_URL=http://localhost:8000
SERVICE_KEY=<must exactly match backend's SUPABASE_SERVICE_KEY>
CAMERA_SOURCE=0
CONFIDENCE_THRESHOLD=0.5
FENCE_ZONE=[[100,100],[400,100],[400,400],[100,400]]
```

## Run
```bash
# from the project root, one level above ai/
python -m ai.main --camera-id <uuid-of-an-existing-backend-camera>
```
The camera ID must already exist in the backend (create one via `POST /cameras` first) — this module doesn't create one for you.

## Demo without a real camera
Generate a short synthetic test clip (a moving "car" shape with a
readable plate, crossing a marked zone) — useful for testing the
plumbing, NOT a substitute for real footage in an actual demo (see
the caveat in the script's docstring):
```bash
python -m ai.tests.make_demo_video demo_video.mp4
```
Run the pipeline against it, looping so a short clip keeps a live demo
going instead of the pipeline just stopping when the file ends:
```bash
python -m ai.main --camera-id <camera-id> --source demo_video.mp4 --loop
```
For an actual demo (not just plumbing verification), use a real short
traffic/surveillance video clip as `--source` instead — YOLO needs real
visual features to detect a "car," not a plain colored rectangle.

## ANPR flow (vehicle detected -> plate read -> alert)
`pipeline.py` now wires this up end to end: when the detector reports a
vehicle-class object (`car`/`truck`/`bus`/`motorcycle`), `ANPRProcessor`
crops that vehicle's region, searches it for a plate-shaped candidate,
runs OCR, and — if a plausible plate string comes back — reports an
`"anpr"` alert (mapped to backend's real `unauthorized_vehicle` enum
value). Debounced per track ID (60-frame cooldown) so the same vehicle
sitting in frame doesn't spam one alert per frame.

## What's actually verified vs. what isn't

I built and tested this by actually running it — not just writing code and assuming it works. Here's the honest breakdown:

**Verified with real, passing tests (13/13):**
- `tracking/tracker.py` — ID stability across frames, new-object assignment, stale-track eviction
- `intrusion/virtual_fence.py` — enter/exit/re-enter debouncing (fires exactly once per crossing, not once per frame inside the zone)
- `activity/activity_detector.py` — rapid movement vs. loitering heuristics
- `utils/backend_client.py` — request shape, alert_type mapping, error handling on bad responses (mocked HTTP, run via `pytest`)

**Verified live, against a real running backend (not mocked):**
- `send_detection()` actually POSTed to a live FastAPI backend and got back a real 201 + persisted alert record.
- **Full ANPR wiring** (`pipeline.py` + `anpr/anpr_processor.py`) — tested with a fake `Detector` reporting a "car" (since real YOLO can't run here — see below) but 100% real plate cropping, real OCR, real alert-type mapping, and real per-track debounce. Confirmed: a vehicle detection with a plate in frame fires exactly one `anpr` alert (not once per frame), a non-vehicle class never triggers ANPR, and the alert correctly maps to backend's `unauthorized_vehicle` enum value.
- **Demo video generation and looping** — `make_demo_video.py` produces a real, valid video file; confirmed a video source can be reopened and re-read in full after reaching its end (the mechanism `--loop` relies on).

**Verified with real image data (not just "didn't crash"):**
- `face/face_detector.py` — correctly found 1 face at a sane bounding box on a real photo, and correctly found 0 faces on blank/noise images.
- `anpr/plate_detector.py` + `anpr/ocr.py` — found the plate-shaped region in a synthetic test image and OCR'd the text back **exactly correctly** end to end.

**NOT verified here — needs your machine:**
- `detection/detector.py` (YOLOv8 via `ultralytics`) — I could not install `torch`/`ultralytics` in my sandbox (ran out of disk space even after cleanup). The code is written correctly and *imports* cleanly (confirmed the lazy import doesn't require torch just to load the module), but I have not run real inference with it. Test this yourself:
  ```python
  from ai.detection.detector import Detector
  import cv2
  d = Detector()  # downloads yolov8n.pt automatically on first run
  frame = cv2.imread("some_test_image.jpg")
  print(d.detect(frame))
  ```
- Actual webcam/video file capture (`video/video_stream.py`) — no camera available in my sandbox. The `cv2.VideoCapture` wrapper is standard and should work, but confirm it opens your real source.
- `pipeline.py` end-to-end with a real camera feed — each piece is verified individually; running the full loop against live video is the integration step you'll want to do first.

## Known simplifications (by design, for a prototype)
- `plate_detector.py` uses a contour/edge heuristic, not a trained model — expect more false positives on cluttered real-world footage than on the clean synthetic test image above.
- `tracker.py` is a simple centroid-distance matcher — fine for a handful of objects, will misbehave with many overlapping/crossing tracks. Swap for `ultralytics`'s built-in `.track()` or ByteTrack/DeepSORT if that becomes a problem.
- `alert_type` mapping in `backend_client.py` — backend's real `AlertType` enum doesn't have dedicated `face`/`anpr`/`activity` values, so this module maps them onto the closest existing type (`suspicious_activity`, `unauthorized_vehicle`, etc.). Check `ALERT_TYPE_MAP` in `utils/backend_client.py` if backend's enum changes.

### Browser camera preview
The AI process now publishes the exact captured frames as an MJPEG stream so the dashboard can show the camera that the AI process is using. By default it is available at `http://localhost:8001/stream.mjpg`.

If a camera is created with `stream_url=0` (or no stream URL), the dashboard uses this preview automatically. For an external browser-compatible stream, enter its HTTP/MJPEG/HLS URL instead. RTSP is not directly playable by normal browsers; convert RTSP to MJPEG/HLS/WebRTC first.

Use `--no-preview` to disable the preview server.
