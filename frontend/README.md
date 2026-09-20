# Border Sentinel — Frontend

## Run it correctly
Do **not** double-click `index.html`. This is a Vite/React application and must be served by Vite.

### Windows
```bat
cd frontend
npm install
copy .env.example .env
npm start
```
Then open the URL Vite prints (normally `http://localhost:5173`).

### macOS / Linux
```bash
cd frontend
npm install
cp .env.example .env
npm start
```

`npm run dev` is also supported.

## Backend connection
The frontend reads `VITE_BACKEND_URL` from `frontend/.env`. The example file already points to `http://localhost:8000`.

If the backend is running on another machine, change it to that machine's URL and add the frontend origin to `backend/.env` under `CORS_ORIGINS`.

## Live laptop webcam
The browser UI displays the annotated MJPEG stream produced by the AI service. Start the AI service with webcam source `0`, then open **Cameras -> View camera**. The Cameras list intentionally has no live previews so multiple streams are not loaded at once.

## Uploaded video
Use **Analyze** or the upload section on a camera detail page. The AI upload API runs on port `8002` and the annotated preview is served on port `8001`.
