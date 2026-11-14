"""HTTP event delivery with best-effort durable JSONL queue when backend is down."""
import json
import os
from pathlib import Path
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen
from dotenv import load_dotenv

load_dotenv()
API_URL = os.getenv("API_URL", "http://127.0.0.1:8000").rstrip("/")
QUEUE_FILE = Path("data/pending_events.jsonl")

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

def flush_pending():
    if not QUEUE_FILE.exists():
        return
    pending = [json.loads(line) for line in QUEUE_FILE.read_text(encoding="utf-8").splitlines() if line.strip()]
    remaining = []
    for n, event in enumerate(pending):
        try:
            _post(event)
        except (URLError, HTTPError, OSError, RuntimeError):
            remaining = pending[n:]
            break
    if remaining:
        QUEUE_FILE.write_text("".join(json.dumps(item) + "\n" for item in remaining), encoding="utf-8")
    else:
        QUEUE_FILE.unlink(missing_ok=True)

def send_event(event: dict) -> None:
    flush_pending()
    try:
        _post(event)
        print("[SENT]", event["hazard_type"])
    except (URLError, HTTPError, OSError, RuntimeError) as exc:
        QUEUE_FILE.parent.mkdir(parents=True, exist_ok=True)
        with QUEUE_FILE.open("a", encoding="utf-8") as queue:
            queue.write(json.dumps(event) + "\n")
        print("[QUEUED]", event["hazard_type"], "-", exc)
