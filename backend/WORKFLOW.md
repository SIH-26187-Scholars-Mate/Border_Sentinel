# Border Sentinel camera workflow

## What changed

The backend now owns AI worker lifecycle. Creating an active camera automatically starts one `python -m ai.main` worker for that camera. Updating its RTSP URL or active state restarts/stops the worker, and deleting the camera stops it.

Each worker gets its own preview port: `AI_PREVIEW_BASE_PORT + camera_number` (default base `8100`, so CAM-001 uses `8101`). This prevents multiple camera workers from fighting over one MJPEG server port.

The frontend never starts an AI command and never asks the operator to copy a camera UUID. `View Camera` consumes the per-camera preview URL returned by the backend.

## Add an IP camera

In **Cameras -> Add camera** enter:

- Camera name: `Border Gate 01`
- Location: `North Gate`
- RTSP / Stream URL: `rtsp://USER:PASSWORD@CAMERA_IP:554/STREAM_PATH`
- Latitude/longitude if desired
- Keep **Camera active** checked

Click **Create camera**. The backend saves the camera and launches its AI worker automatically.

## Where to get an RTSP URL

The RTSP URL comes from the camera or NVR configuration, not from Border Sentinel. Common places:

1. The IP camera manufacturer's web/admin page: look under Network, Streaming, RTSP, Video, or ONVIF.
2. An NVR/DVR: open the channel/stream information and copy its RTSP URL.
3. The camera manual/specification: search the exact model for its RTSP path.
4. ONVIF Device Manager or a similar ONVIF discovery tool can help identify the camera and available profiles on a local network.
5. VLC can test a URL before adding it: Media -> Open Network Stream.

A typical URL looks like:

`rtsp://username:password@192.168.1.100:554/stream1`

The exact path is manufacturer/model-specific. Do not put a fake RTSP URL in the demo and claim it is live.

## Laptop webcam demo

Leave the RTSP field blank. Border Sentinel treats an empty source as webcam index `0`. The backend still creates a normal camera record and automatically starts its AI worker.

## Runtime requirements

Run the backend and frontend normally. The machine running the backend must also have the AI Python dependencies/model available because the backend launches the AI child processes locally. For a real RTSP camera, that machine must be able to reach the camera over the network.

Set these in `backend/.env`:

- `AI_SERVICE_KEY` — secret shared with the AI workers
- `BACKEND_URL` — normally `http://localhost:8000`
- `AI_PREVIEW_BASE_PORT` — optional, default `8100`

The worker receives `BACKEND_URL`, `SERVICE_KEY`, and its unique preview port automatically. You no longer need a separate AI terminal for each camera.

## Demo sequence

1. Start backend.
2. Start frontend.
3. Log in.
4. Add an active camera with an RTSP URL (or leave it blank for laptop webcam).
5. The backend automatically starts that camera's AI worker.
6. Open **View Camera**.
7. The live annotated feed appears.
8. Draw/save a restricted zone.
9. Trigger an intrusion or vehicle/plate event.
10. Open **Alerts** and use **View Camera** to jump back to the source camera.
