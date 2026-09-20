# Border Sentinel

A border surveillance prototype: FastAPI backend, an AI detection pipeline
(YOLOv8 + tracking + intrusion/face/ANPR/activity detection), and a React
dashboard — talking to each other over a real HTTP + WebSocket contract.

```
border-sentinel/
  backend/    FastAPI + Supabase auth, REST API, WebSocket alert feed
  ai/         Video capture -> detection -> tracking -> alerts (posts into backend)
  frontend/   React + Vite dashboard (login, cameras, live alerts)
```

Each folder also has its own README with more detail — this one is the
"how do I actually run the whole thing" guide.

---

### Recorded-video history and persistence

Uploaded-video analysis is persisted through the backend's Supabase `alerts` table. The AI service first finishes reading the entire video, then writes one history record per detected object class (plus face findings/events where applicable). These records are therefore visible from the dashboard/camera history and survive backend restarts.

Keep `DATABASE_MODE=supabase` in `backend/.env` for real persistence. Do **not** use `DATABASE_MODE=memory` except for tests; memory mode is intentionally cleared when the backend process stops. If Supabase is unavailable or the schema is missing, the backend now returns a persistence error instead of silently pretending the data was saved.

If you are upgrading an existing installation, run `backend/supabase_schema.sql` again in the Supabase SQL Editor before testing.

## Before you start

You need a Supabase project (free tier is fine). If you haven't set one up:
1. Create a project at supabase.com
2. Run `backend/supabase_schema.sql` in the Supabase SQL Editor to create/update the persistent `cameras` and `alerts` tables (the script also adds stable camera numbers such as `CAM-001`)
3. Grab your Project URL, anon key, and service_role key from
   Project Settings -> API
4. Add a test user under Authentication -> Users

Check Project Settings -> API -> JWT Keys: if you see "JWT Signing Keys"
(asymmetric, no plain secret) rather than a "Legacy JWT Secret", your
backend needs `SUPABASE_JWKS_URL` set — it already is, correctly, in
`backend/.env.example`.

---

## 0. Set up the Python environment (once)

backend/ and ai/ share **one** venv at the project root — the backend
launches the AI module as a child process, so keeping them in separate
environments only risks version drift for no benefit.

```bash
./setup.sh                # Linux/macOS — creates .venv, installs requirements.txt
# or on Windows:
setup_windows.bat
```
Also needed for OCR (license plate reading) to work at all:
```bash
sudo apt install tesseract-ocr      # Ubuntu/Debian
brew install tesseract               # macOS
```
Activate it in every terminal you use below: `source .venv/bin/activate`
(`.venv\Scripts\activate` on Windows).

---

## 1. Start the backend first

```bash
cd backend
cp .env.example .env
# edit .env: fill in SUPABASE_URL, SUPABASE_ANON_KEY, SUPABASE_SERVICE_KEY, AI_SERVICE_KEY

uvicorn app.main:app --reload
```
Confirm it's alive: open `http://localhost:8000/health` — should return
`{"status": "ok"}`. Also check `http://localhost:8000/docs` for the full
interactive API.

Run the test suite while you're here, just to confirm nothing broke in transit:
```bash
pytest
```
Should show `34 passed`.

**Create at least one camera before moving on** — everything downstream
(AI ingest, frontend camera pages) expects a real camera to exist. Easiest
way: use the `/docs` page, log in via `POST /auth/login` with your test
user, authorize with the returned token, then use `POST /cameras` to
create one. **Copy the camera's `id`** — you'll need it for the AI module.

Leave this terminal running.

---

## 2. Start the frontend

Open a **new terminal**:
```bash
cd frontend
npm install
cp .env.example .env       # only needed if backend isn't on localhost:8000
npm start
```
Open the printed URL (usually `http://localhost:5173`). **Do not open `frontend/index.html` directly.** Log in with the
same test user credentials you created in Supabase. You should land on the
Dashboard with an empty alert feed and a green "Live" indicator (meaning
the WebSocket connected).

Leave this terminal running too.

---

## 3. Start the AI module

Open a **third terminal** (same venv from step 0 — `source .venv/bin/activate`):
```bash
cd ai
cp .env.example .env
# edit .env: SERVICE_KEY must exactly match backend/.env's AI_SERVICE_KEY
```

Run it against the camera you created in Step 1:
```bash
python -m ai.main --camera-id <the-camera-id-you-copied-earlier>
```
By default this opens webcam index 0. To use a video file instead:
```bash
python -m ai.main --camera-id <camera-id> --source /path/to/test-video.mp4
```

---

## 4. Watch it work end to end

With all three running, walk (or wave, or point a phone) in front of the
camera. If it crosses the zone defined in `ai/.env`'s `FENCE_ZONE`, you
should see a new alert appear **live, with no refresh** on the frontend's
Dashboard within a second or two — that's the whole pipeline working:
camera -> AI detection -> backend alert -> WebSocket -> dashboard.

If nothing shows up, check in this order:
1. Backend terminal — did a `POST /ingest/detection` request show up in
   its logs at all? If not, the AI module isn't reaching it (check
   `BACKEND_URL` and `SERVICE_KEY` in `ai/.env`).
2. If the backend logged a 403, `SERVICE_KEY` doesn't match
   `SUPABASE_SERVICE_KEY` — they must be identical.
3. If the backend logged a 201 (success) but nothing appeared on the
   dashboard, check the browser console for WebSocket connection errors,
   and confirm the frontend's "Live" indicator is actually green.

---

## Honest status (read this before assuming everything "just works")

- Backend: fully tested, 34/34 automated tests passing, real Supabase auth
  verified live. **Uses Supabase/Postgres persistence by default** — cameras and alerts survive
  backend restarts and browser refreshes. Tests force `DATABASE_MODE=memory` so
  they remain deterministic and never touch the real Supabase project.
- AI module: tracking, virtual fence, activity detection, face detection,
  ANPR, and the backend integration are all individually tested and
  verified working. **YOLO/torch object detection itself has not been
  run** in the environment this was built in (disk constraints) — test
  `ai.detection.detector.Detector` yourself first before trusting it in
  the full pipeline.
- Frontend: builds and serves cleanly, every API call matches backend's
  real schemas, and the live WebSocket path was verified with a real
  message round-trip. **The actual logged-in browser experience has not
  been visually checked** — you're the first to actually see it rendered
  and click through it for real.

## UI/UX demo flow

The frontend deliberately does **not** render live video previews on the
Cameras list. Live video is opened only after the operator clicks **View
camera**. This avoids loading multiple MJPEG streams at once and keeps the
main dashboard responsive. Dashboard and Alerts show the camera code/name
that generated each alert and provide a direct **View camera** link.

The **Analyze** page provides a global recorded-video workflow. Choose a
camera, upload a supported video, and review the AI-annotated preview. The AI
preview server uses a separate preview channel for each upload job so an
uploaded-video preview does not overwrite the selected camera's live feed.

## Operations dashboard design
The frontend is intentionally event-centric rather than rendering every camera stream at once. It borrows useful product patterns from the reviewed Chitra video-processing dashboard: a decoupled processing layer, centralized alert API, responsive React UI, searchable/filterable event queues, evidence review, and operational status visibility. The Border Sentinel implementation remains domain-specific to border surveillance and keeps live camera playback on demand.

## Team / Contributors

| Name | GitHub | Contribution |
|---|---|---|
| Prakash | [@Prakashsingh2007](https://github.com/Prakashsingh2007) | Development — backend, AI pipeline, frontend |
| Nitish Solanki | [@Nitish6769](https://github.com/Nitish6769) | Ideas / planning / debugging|