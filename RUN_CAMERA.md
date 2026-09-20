# Border Sentinel - Camera Run Guide

## Local laptop webcam
1. Run `setup_windows.bat` once on Windows (or install both backend and AI requirements into the same Python environment).
2. Start FastAPI from the repository root:
   `.venv\Scripts\python.exe -m uvicorn backend.app.main:app --reload --port 8000`
3. Start the React frontend with `cd frontend && npm install && npm start`.
4. Open `http://localhost:5173`.
5. Add a camera with an empty Stream URL to use the laptop webcam (`source 0`).
6. Open **View Camera** and press **Start camera**. The backend launches the AI worker automatically.

## RTSP camera
Enter the complete RTSP URL when creating the camera, for example:
`rtsp://username:password@192.168.1.100:554/stream1`
The backend passes it directly to the AI worker; no terminal command or camera UUID copy/paste is required.

## If Start Camera fails
Open `runtime/ai-logs/CAM-001.log` (or the matching camera number). The dashboard also displays the worker startup error. Common causes are missing AI dependencies, webcam permission/use by another application, or an unreachable/incorrect RTSP URL.

## Important architecture fix
The camera worker does **not** start the upload-video API. That API remains a separate service on port 8002, preventing multiple camera workers from fighting over the same upload port.
