# SiteGuardian AI — DurHack 2026

**SiteGuardian** is a hackathon prototype for construction-site near-miss monitoring. Edge computer vision detects virtual-zone intrusion and prolonged exposure, triggers an immediate local alert, and sends events to a Python API. **MongoDB** stores incident history; **Google Gemini API** explains observed patterns and suggests preventive measures for human review. A **React** dashboard shows live results.

> Demonstration only — NOT certified life-safety equipment, a substitute for physical safeguards, or safe for real construction-site deployment.

## Quick start (Windows PowerShell)

Prerequisites: Python 3.11+, Node.js 20+, Git. To use real storage and analysis, obtain a MongoDB Atlas URI and Gemini API key.

```powershell
git clone https://github.com/Mohanadtalal/durhack2026.git
cd durhack2026
Copy-Item .env.example .env
py -m venv .venv
.venv\Scripts\Activate.ps1
pip install -r backend/requirements.txt -r backend/requirements-dev.txt
python -m uvicorn backend.app.main:app --reload
```

Open a **second terminal**:

```powershell
cd durhack2026/frontend
npm install
npm run dev
```

Dashboard: http://localhost:5173 · API documentation: http://127.0.0.1:8000/docs

Open a **third terminal**, in repository root, to send simulated events:

```powershell
python -m edge.demo
```

You can test the full API and dashboard without a webcam. If `MONGODB_URI` is not supplied, the API uses temporary **in-memory demo storage**. Put the MongoDB URI and `GEMINI_API_KEY` in your local `.env` to enable actual persistence and LLM insights. Never commit the file.

### Optional camera detector

```powershell
pip install -r edge/requirements-vision.txt
python -m edge.camera
```

This attempts real-time person detection inside a rectangular virtual hazard zone. The first run may download model weights. Press `q` to quit. See `docs/ARCHITECTURE.md` for limitations.

## Repository structure

- `backend/app` — FastAPI endpoints, MongoDB integration, Gemini service
- `backend/tests` — API contract tests
- `edge` — local hazard rules, simulated node, optional webcam node and event queue
- `edge/tests` — deterministic rule tests
- `frontend` — Vite + React dashboard
- `hardware` — optional Arduino serial-alert sketch
- `docs` — architecture, API and demo roadmap
- `.github/workflows` — CI tests and frontend build

## Team responsibilities

| Person | Primary responsibility | Suggested branch |
|---|---|---|
| 1 | Edge camera, zone rules and local warning | `feat/edge-vision` |
| 2 | Backend, MongoDB, REST API | `feat/backend-data` |
| 3 | Gemini insight agent, pattern evidence | `feat/gemini-analysis` |
| 4 | Frontend, integration, demo | `feat/dashboard` |

Create pull requests into `main` and coordinate schema changes. See `CONTRIBUTING.md`.

## Scope and status

Functional scaffold: core zone rule engine, simulated events, API, MongoDB adapter, Gemini integration, basic dashboard, CI/tests. **No physical board, live camera, MongoDB cluster or Gemini account has yet been verified by the team.** Hard-hat detection, collision prediction, precise distances and multi-camera tracking are stretch features, not claimed functionality.
