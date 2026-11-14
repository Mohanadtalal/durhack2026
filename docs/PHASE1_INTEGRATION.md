# Phase 1 — Connected local integration

SiteGuardian's Nicla detector can now publish its **annotated OpenCV view**
over a local MJPEG endpoint and advertise its **real saved zone polygons**
to the dashboard. The feature is entirely optional and off by default.

This is for controlled, localhost hackathon demos. **Not authenticated,
encrypted, hardened or suitable for exposure to a site network or Internet.**

## 1. Prepare and start backend

Use Windows PowerShell in the project root, with Python environment activated.

```powershell
git switch feat/phase1-live-integration
git pull --ff-only origin feat/phase1-live-integration
pip install -r backend/requirements.txt -r backend/requirements-dev.txt
pip install -r edge/requirements-vision.txt -r edge/requirements-hardware.txt
python -m uvicorn backend.app.main:app --reload
```

Without `MONGODB_URI` configured the API will use in-memory incident
storage. `GEMINI_API_KEY` is optional for incident ingestion; live Gemini
analysis requires the team's key on their own local computer.

## 2. Start the dashboard in a separate PowerShell window

Copy `frontend/.env.example` to `frontend/.env`, and set:

```dotenv
VITE_API_BASE=http://127.0.0.1:8000
VITE_CAMERA_URL=http://127.0.0.1:8765/stream.mjpg
VITE_CAMERA_MODE=stream
VITE_CAMERA_LABEL=Nicla Vision
```

```powershell
cd frontend
npm ci
npm run dev
```

Open `http://localhost:5173`. The camera panel should initially show
that no recent frame is available. **Never claim a device is online merely
because the API or image URL exists.**

## 3. Connect Nicla in a third PowerShell window

Use the same machine for all three terminals:

```powershell
python -m edge.nicla_detector --port COM9 --predictive --motion-debug --stream-port 8765
```

This:
- Reads raw frames from Nicla Vision over USB serial.
- Runs optional motion detection and annotated overlay on your host laptop.
- Publishes `http://127.0.0.1:8765/stream.mjpg` for the camera UI.
- Publishes `http://127.0.0.1:8765/status.json` with `connected`,
  `last_frame_age_seconds` and normalized `nicla-zone-1` etc polygons.
- Sends genuine, distinct detections as incidents to the separate FastAPI
  service, including actual IDs such as `nicla-zone-1`.

Press **E**, click at least three points, **S** to save a restricted zone,
and observe the same polygon in **Camera zones** in the web UI after the
next status poll. Press **R** to clear zones. For predictive vehicle/worker
approaches, marking any road area is **NOT required**.

Try a safe demonstration with an object or an actor walking into the
restricted zone; avoid unsafe work or intentionally creating near misses.

## 4. Check connections and common problems

```powershell
Invoke-RestMethod http://127.0.0.1:8000/api/health
Invoke-RestMethod http://127.0.0.1:8765/status.json
```

Expected when frames arrive: `connected: true` and real `zones` array.
After unplugging Nicla or stopping the stream, camera status becomes
disconnected within five seconds. The API health check is unrelated to
camera readiness; don't confuse them.

The preview service binds to localhost by default. For teammates viewing
a remote machine's camera, use an authenticated reverse proxy with TLS in
a future iteration; do NOT expose `--stream-host 0.0.0.0` on public or
untrusted networks. The demo endpoint has no built-in login or encryption.

Camera polygons are **image-relative camera regions**, not a surveyed site
plan. An incident without a known polygon is listed by ID, not invented
on the map. The app currently has no protected device authentication,
no central site geometry registry and no production video transport.

## 5. Automated verification

```powershell
python -m pytest backend/tests edge/tests -q
npm --prefix frontend run build
```

The new HTTP stream service has tests for frame freshness and zone schema.
Real Nicla image output, local LED activation, the entire deployed camera
network and a live Gemini account still require hands-on integration checks.
