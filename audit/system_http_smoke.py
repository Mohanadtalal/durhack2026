"""Real HTTP smoke test for the SiteGuardian demo services.

Runs against a live local FastAPI process, exercising edge -> HTTP ->
in-memory storage -> stats -> Gemini missing-key error -> offline queue replay.
No real camera, MongoDB Atlas or Gemini API is used.
"""
import json
import os
from pathlib import Path
from urllib.error import HTTPError
from urllib.request import Request, urlopen

import edge.client as edge_client
from edge.demo import make_event
from edge.zone_rules import ZoneMonitor

API = os.getenv("API_URL", "http://127.0.0.1:8000").rstrip("/")


def request(method, path, body=None):
    payload = json.dumps(body).encode() if body is not None else None
    req = Request(API + path, data=payload, method=method,
                  headers={"Content-Type": "application/json"})
    try:
        with urlopen(req, timeout=10) as response:
            return response.status, json.load(response)
    except HTTPError as exc:
        return exc.code, json.load(exc)


def check(condition, message):
    if not condition:
        raise AssertionError(message)
    print("[E2E PASS] " + message)


def main():
    code, health = request("GET", "/api/health")
    check(code == 200 and health["status"] == "ok", "Live backend health")
    check(health["storage_mode"] == "memory", "Isolated memory-store demo mode")

    # Exercise the actual edge zone transition rules and HTTP delivery client.
    monitor = ZoneMonitor(dwell_seconds=1)
    emitted = []
    for inside, t in ((False, 0), (True, 1), (True, 1.2),
                      (True, 2.2), (True, 2.3), (False, 3)):
        for kind in monitor.update(inside, t):
            event = make_event(kind)
            event["zone_id"] = "nicla-zone-1"
            emitted.append(event)
            edge_client.send_event(event)
    check([e["hazard_type"] for e in emitted] == [
        "zone_entry", "prolonged_exposure",
    ], "Zone-entry and dwell rules emit exactly once")

    code, events = request("GET", "/api/events?limit=30")
    ids = [e["event_id"] for e in events]
    check(code == 200 and all(e["event_id"] in ids for e in emitted),
          "Edge client events reached the HTTP API and storage")
    check(all(e["zone_id"] == "nicla-zone-1"
              for e in events if e["event_id"] in [x["event_id"] for x in emitted]),
          "Nicla-generated zone IDs persist correctly")

    # Retry the identical payload and prove server-side idempotency.
    code, _ = request("POST", "/api/events", emitted[0])
    _, events = request("GET", "/api/events?limit=30")
    check(code == 200 and sum(e["event_id"] == emitted[0]["event_id"]
                              for e in events) == 1, "Duplicate incident replay is idempotent")

    code, stats = request("GET", "/api/stats")
    check(code == 200 and
          stats["by_hazard"].get("zone_entry", 0) >= 1 and
          stats["by_hazard"].get("prolonged_exposure", 0) >= 1,
          "Statistics reflect stored incident history")

    code, failure = request("POST", "/api/insights")
    check(code == 503 and "GEMINI_API_KEY" in failure.get("detail", ""),
          "No-key Gemini path has an explicit non-success response")

    code, failure = request("POST", "/api/events", {"hazard_type": "zone_entry"})
    check(code == 422, "Invalid event is rejected by Pydantic")

    # Simulate an outage using an unreachable local port, then replay when up.
    original_url, original_queue = edge_client.API_URL, edge_client.QUEUE_FILE
    queue = Path("data/audit_e2e_pending.jsonl")
    queue.unlink(missing_ok=True)
    queued_event = make_event("zone_entry")
    try:
        edge_client.API_URL = "http://127.0.0.1:65531"
        edge_client.QUEUE_FILE = queue
        edge_client.send_event(queued_event)
        check(queue.exists() and queue.stat().st_size > 0,
              "Offline event queued while backend unavailable")
        edge_client.API_URL = API
        edge_client.flush_pending()
        check(not queue.exists(), "Queued event flushed after reconnect")
        _, events = request("GET", "/api/events?limit=30")
        check(any(e["event_id"] == queued_event["event_id"] for e in events),
              "Replayed event stored by backend")
    finally:
        edge_client.API_URL, edge_client.QUEUE_FILE = original_url, original_queue
        queue.unlink(missing_ok=True)

    print("[E2E] All local HTTP and edge offline replay smoke checks passed.")
    print("[E2E] Limits: no live Nicla, physical LED, Atlas or live Gemini API.")


if __name__ == "__main__":
    main()
