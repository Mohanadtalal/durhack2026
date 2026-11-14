"""REST service, local prototype only: no authentication. Do not expose publicly."""
from collections import Counter

from fastapi import FastAPI, HTTPException, Query
from fastapi.middleware.cors import CORSMiddleware
from pymongo.errors import PyMongoError

from .config import GEMINI_MODEL
from .gemini_service import analyze_incidents
from .models import Incident, Insight
from .storage import store

app = FastAPI(title="SiteGuardian AI", version="0.1.0")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_methods=["GET", "POST"],
    allow_headers=["Content-Type"],
)

@app.get("/api/health")
def health():
    return {"status": "ok", "storage_mode": store.mode}

@app.post("/api/events", response_model=Incident)
def create_event(event: Incident):
    try:
        return store.save(event)
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="MongoDB unavailable") from exc

@app.get("/api/events")
def events(limit: int = Query(default=30, ge=1, le=200)):
    try:
        return store.recent(limit)
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="MongoDB unavailable") from exc

@app.get("/api/stats")
def stats():
    try:
        all_events = store.recent(200)
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="MongoDB unavailable") from exc
    return {
        "total": len(all_events),
        "by_hazard": dict(Counter(e["hazard_type"] for e in all_events)),
        "by_zone": dict(Counter(e["zone_id"] for e in all_events)),
        "by_severity": dict(Counter(e["severity"] for e in all_events)),
        "note": "Counts cover the latest 200 incident records.",
    }

@app.post("/api/insights", response_model=Insight)
def insights():
    try:
        all_events = store.recent(100)
    except PyMongoError as exc:
        raise HTTPException(status_code=503, detail="MongoDB unavailable") from exc
    if not all_events:
        raise HTTPException(status_code=404, detail="No incidents to analyse")
    try:
        summary = analyze_incidents(all_events)
    except RuntimeError as exc:
        raise HTTPException(status_code=503, detail=str(exc)) from exc
    except Exception as exc:
        raise HTTPException(status_code=502, detail="Gemini request failed") from exc
    return Insight(summary=summary, model=GEMINI_MODEL, events_analyzed=len(all_events))
