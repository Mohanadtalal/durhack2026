"""REST service, local prototype only: no authentication. Do not expose publicly."""
from collections import Counter

from fastapi import FastAPI, HTTPException, Query, Request
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware
from pymongo.errors import PyMongoError

from .config import GEMINI_MODEL
from .gemini_service import analyze_incidents
from .evidence import MAX_SNAPSHOT_BYTES, file_for, save_snapshot
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


@app.post("/api/snapshots/{event_id}")
async def upload_snapshot(event_id: str, request: Request):
    """Store evidence before posting the associated incident record.

    Raw JPEG only; bounded streamed read avoids unbounded request-body memory.
    """
    if request.headers.get("content-type", "").split(";")[0].lower() != "image/jpeg":
        raise HTTPException(status_code=415, detail="Expected image/jpeg")
    chunks = []
    total = 0
    async for chunk in request.stream():
        total += len(chunk)
        if total > MAX_SNAPSHOT_BYTES:
            raise HTTPException(status_code=413, detail="JPEG too large")
        chunks.append(chunk)
    url = save_snapshot(event_id, b"".join(chunks))
    return {"snapshot_url": url}


@app.get("/api/snapshots/{event_id}.jpg")
def get_snapshot(event_id: str):
    path = file_for(event_id)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Snapshot not found")
    return FileResponse(path, media_type="image/jpeg", headers={
        "Cache-Control": "private, no-store",
        "X-Content-Type-Options": "nosniff",
    })

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
