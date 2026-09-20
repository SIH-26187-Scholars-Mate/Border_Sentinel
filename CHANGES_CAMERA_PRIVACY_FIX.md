# Camera preview + privacy fix

## Fixed
- Live MJPEG preview now retries automatically if the browser connects before the AI preview server is ready.
- Webcam/RTSP workers no longer exit permanently after a transient camera read failure; they keep the AI worker alive and reconnect.
- Blank, `null`, `none`, `webcam`, and `camera` stream sources resolve to laptop webcam `0` for local testing.
- Explicit **Log out** now calls `POST /cameras/stop-all` before clearing the browser session.
- Stopping workers on Windows now falls back from `CTRL_BREAK_EVENT` to process termination, preventing a webcam handle from being left behind.
- Logging out marks persisted cameras inactive, so cameras do not automatically restart when the next session opens.

## Test result
- Backend test suite: **34 passed**.
- Python source compilation: **OK**.
- Frontend build was not run because `frontend/node_modules` is not included in the ZIP/environment.
