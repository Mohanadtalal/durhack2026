"""Evidence upload is required before exposing a snapshot URL to the UI."""
from uuid import uuid4

from fastapi.testclient import TestClient

from backend.app import evidence
from backend.app.main import app

client = TestClient(app)
JPEG = b"\xff\xd8\xff\xe0" + b"image-data" + b"\xff\xd9"


def test_snapshot_upload_roundtrip(tmp_path, monkeypatch):
    monkeypatch.setattr(evidence, "SNAPSHOT_ROOT", tmp_path)
    event_id = str(uuid4())
    upload = client.post(f"/api/snapshots/{event_id}", content=JPEG,
                         headers={"Content-Type": "image/jpeg"})
    assert upload.status_code == 200
    url = upload.json()["snapshot_url"]
    assert url == f"/api/snapshots/{event_id}.jpg"
    assert (tmp_path / f"{event_id}.jpg").read_bytes() == JPEG
    response = client.get(url)
    assert response.status_code == 200
    assert response.headers["content-type"] == "image/jpeg"
    assert response.content == JPEG


def test_snapshot_missing_invalid_and_oversize(tmp_path, monkeypatch):
    monkeypatch.setattr(evidence, "SNAPSHOT_ROOT", tmp_path)
    event_id = str(uuid4())
    assert client.get(f"/api/snapshots/{event_id}.jpg").status_code == 404
    assert client.get("/api/snapshots/not-a-uuid.jpg").status_code == 422
    assert client.post(f"/api/snapshots/{event_id}", content=b"bad",
                       headers={"Content-Type": "image/jpeg"}).status_code == 413
    assert client.post(f"/api/snapshots/{event_id}", content=b"\xff\xd8\xfftest\xff\xd9",
                       headers={"Content-Type": "text/plain"}).status_code == 415
    assert client.post(f"/api/snapshots/{event_id}", content=JPEG + b"x"*2_000_000,
                       headers={"Content-Type": "image/jpeg"}).status_code == 413
