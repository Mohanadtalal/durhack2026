"""HTTP event delivery with retryable, on-disk evidence staging.

Images are uploaded *before* an incident receives a snapshot_url. A temporary
network outage keeps both the incident and JPEG in the existing pending queue.
"""
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from dotenv import load_dotenv

load_dotenv()
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000").rstrip("/")
QUEUE_FILE = Path("data/pending_events.jsonl")
EVIDENCE_QUEUE_DIR = Path("data/pending_snapshots")


def _post(event: dict) -> None:
    request = Request(
        API_URL + "/api/events",
        data=json.dumps(event).encode("utf-8"),
        method="POST",
        headers={"Content-Type": "application/json"},
    )
    with urlopen(request, timeout=2) as response:
        if not 200 <= response.status < 300:
            raise RuntimeError(f"Unexpected response: {response.status}")


def _upload_snapshot(event_id: str, jpg: bytes) -> str:
    request = Request(
        API_URL + "/api/snapshots/" + event_id,
        data=jpg, method="POST",
        headers={"Content-Type": "image/jpeg"},
    )
    with urlopen(request, timeout=3) as response:
        if not 200 <= response.status < 300:
            raise RuntimeError(f"Evidence upload failed: {response.status}")
        url = json.load(response).get("snapshot_url")
        expected = f"/api/snapshots/{event_id}.jpg"
        if url != expected:
            raise RuntimeError("Evidence server returned an unexpected image URL")
        return url


def _deliver(event: dict, snapshot_path: str | None = None):
    # Repeated upload with the same event ID is safe (an interrupted POST retry).
    payload = {**event, "metadata": dict(event.get("metadata") or {})}
    if snapshot_path:
        jpg = Path(snapshot_path).read_bytes()
        payload["metadata"]["snapshot_url"] = _upload_snapshot(payload["event_id"], jpg)
        payload["metadata"]["snapshot_status"] = "available"
    _post(payload)


def _pending_record(record):
    if "_event" in record:
        return record["_event"], record.get("_snapshot_path")
    return record, None  # compatibility with old JSONL queues


def flush_pending():
    if not QUEUE_FILE.exists():
        return
    pending = [json.loads(line) for line in QUEUE_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
    remaining = []
    for n, record in enumerate(pending):
        event, path = _pending_record(record)
        try:
            _deliver(event, path)
            if path:
                Path(path).unlink(missing_ok=True)
        except (URLError, HTTPError, OSError, RuntimeError, ValueError):
            remaining = pending[n:]
            break
    if remaining:
        QUEUE_FILE.write_text("".join(json.dumps(item) + "\n" for item in remaining), encoding="utf-8")
    else:
        QUEUE_FILE.unlink(missing_ok=True)


def send_event(event: dict, snapshot_jpeg: bytes | None = None) -> None:
    """Stage the captured frame locally, then upload and post as one retry unit.

    If local file I/O fails, the safety event is still reported without an image
    and explicitly marked unavailable rather than linking to a broken URL.
    """
    payload = {**event, "metadata": dict(event.get("metadata") or {})}
    snapshot_path = None
    if snapshot_jpeg:
        try:
            EVIDENCE_QUEUE_DIR.mkdir(parents=True, exist_ok=True)
            target = EVIDENCE_QUEUE_DIR / (payload["event_id"] + ".jpg")
            target.write_bytes(snapshot_jpeg)
            snapshot_path = str(target)
        except OSError as exc:
            payload["metadata"]["snapshot_status"] = "capture_failed"
            print("[EVIDENCE] Cannot stage image:", exc)
    else:
        payload["metadata"]["snapshot_status"] = "capture_unavailable"

    # Attempt earlier queued events without discarding this current incident.
    try:
        flush_pending()
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print("[QUEUE] Existing queue not flushed:", exc)
    try:
        _deliver(payload, snapshot_path)
        if snapshot_path:
            Path(snapshot_path).unlink(missing_ok=True)
        print("[SENT]", payload["hazard_type"],
              "- evidence saved" if snapshot_path else "- no evidence")
    except (URLError, HTTPError, OSError, RuntimeError, ValueError) as exc:
        QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with QUEUE_FILE.open("a", encoding="utf-8") as queue:
            queue.write(json.dumps({"_event": payload, "_snapshot_path": snapshot_path}) + "\n")
        print("[QUEUED]", payload["hazard_type"], "-", exc)
