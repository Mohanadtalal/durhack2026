"""Real temporary MongoDB integration check; no Atlas credentials needed.

Only uses, and only removes, the ephemeral test database siteguardian_e2e_audit.
"""
import os
import time
from uuid import uuid4

from fastapi.testclient import TestClient
from pymongo import MongoClient
from pymongo.errors import ServerSelectionTimeoutError

assert os.getenv("MONGODB_DB") == "siteguardian_e2e_audit"
uri = os.environ["MONGODB_URI"]

for attempt in range(30):
    try:
        MongoClient(uri, serverSelectionTimeoutMS=1000).admin.command("ping")
        break
    except ServerSelectionTimeoutError:
        time.sleep(1)
else:
    raise AssertionError("MongoDB service never became ready")

from backend.app.main import app
from backend.app.storage import MongoStore, store
assert store.mode == "mongodb", "Backend must use real MongoStore, not in-memory"

client = TestClient(app)
payload = {
    "event_id": "audit-" + str(uuid4()),
    "source_id": "site-test-node",
    "zone_id": "nicla-zone-1",
    "hazard_type": "zone_entry",
    "severity": "warning",
    "description": "Safe integration testing; no camera",
    "metadata": {"simulated": True}
}
try:
    h = client.get("/api/health")
    assert h.status_code == 200 and h.json()["storage_mode"] == "mongodb"
    resp = client.post("/api/events", json=payload)
    assert resp.status_code == 200, resp.text
    twice = client.post("/api/events", json=payload)
    assert twice.status_code == 200
    seen = client.get("/api/events?limit=30")
    assert seen.status_code == 200
    assert sum(e["event_id"] == payload["event_id"] for e in seen.json()) == 1
    new_store = MongoStore(uri, "siteguardian_e2e_audit")
    assert any(e["event_id"] == payload["event_id"]
               for e in new_store.recent(30))
    stats = client.get("/api/stats")
    assert stats.status_code == 200
    assert stats.json()["by_zone"]["nicla-zone-1"] == 1
    print("[MONGO E2E PASS] FastAPI POST -> MongoDB persistence -> "
          "unique event ID -> new store process -> stats")
finally:
    MongoClient(uri).drop_database("siteguardian_e2e_audit")
