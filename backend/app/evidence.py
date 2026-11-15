"""Local evidence images for SiteGuardian incidents (prototype, no authentication).

All image paths are UUID-derived and are written atomically. Keep this service
on localhost; snapshots may contain identifiable people.
"""
import os
from pathlib import Path
from uuid import UUID, uuid4

from fastapi import HTTPException

MAX_SNAPSHOT_BYTES = 2_000_000
SNAPSHOT_ROOT = Path(os.getenv("SITEGUARDIAN_SNAPSHOT_DIR", "data/snapshots"))


def canonical_id(event_id: str) -> str:
    try:
        return str(UUID(event_id))
    except (ValueError, AttributeError) as exc:
        raise HTTPException(status_code=422, detail="Expected a UUID event ID") from exc


def file_for(event_id: str) -> Path:
    return SNAPSHOT_ROOT / (canonical_id(event_id) + ".jpg")


def save_snapshot(event_id: str, data: bytes) -> str:
    event_id = canonical_id(event_id)
    if not 4 <= len(data) <= MAX_SNAPSHOT_BYTES:
        raise HTTPException(status_code=413, detail="JPEG size outside allowed range")
    if not (data.startswith(b"\xff\xd8\xff") and data.endswith(b"\xff\xd9")):
        raise HTTPException(status_code=415, detail="Invalid JPEG image")
    SNAPSHOT_ROOT.mkdir(parents=True, exist_ok=True)
    target = SNAPSHOT_ROOT / (event_id + ".jpg")
    temp = SNAPSHOT_ROOT / ("." + event_id + "." + uuid4().hex + ".tmp")
    try:
        temp.write_bytes(data)
        os.replace(temp, target)
    finally:
        temp.unlink(missing_ok=True)
    return f"/api/snapshots/{event_id}.jpg"
