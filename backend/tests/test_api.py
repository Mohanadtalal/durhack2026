from fastapi.testclient import TestClient
from backend.app.main import app

client = TestClient(app)

def test_health():
    r = client.get("/api/health")
    assert r.status_code == 200
    assert r.json()["storage_mode"] in ("memory", "mongodb")

def test_post_and_get_event_idempotent():
    record = {
        "source_id": "test-01", "zone_id": "zone-A",
        "hazard_type": "zone_entry", "severity": "warning",
        "description": "test detection", "metadata": {"demo": True}
    }
    response = client.post("/api/events", json=record)
    assert response.status_code == 200
    event = response.json()
    assert client.post("/api/events", json=event).status_code == 200
    saved = client.get("/api/events").json()
    assert sum(row["event_id"] == event["event_id"] for row in saved) == 1

def test_reject_invalid_event():
    assert client.post("/api/events", json={"zone_id": "zone-A"}).status_code == 422
