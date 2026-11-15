"""Incident + JPEG delivery is retried as a unit after transient outages."""
from copy import deepcopy
from urllib.error import URLError

from edge import client


def _event():
    return {
        "event_id": "b08272b3-9d0a-477e-82d7-50b685aff8ac",
        "hazard_type": "zone_entry",
        "metadata": {"camera": "nicla_vision"},
    }


def test_upload_precedes_event_and_cleans_local_image(tmp_path, monkeypatch):
    monkeypatch.setattr(client, "QUEUE_FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(client, "EVIDENCE_QUEUE_DIR", tmp_path / "jpg")
    calls = []
    monkeypatch.setattr(client, "_upload_snapshot",
                        lambda event_id, data: calls.append(("upload", data)) or
                        f"/api/snapshots/{event_id}.jpg")
    monkeypatch.setattr(client, "_post", lambda event: calls.append(("post", deepcopy(event))))
    client.send_event(_event(), b"test-jpeg")
    assert [kind for kind, _ in calls] == ["upload", "post"]
    assert calls[1][1]["metadata"]["snapshot_status"] == "available"
    assert calls[1][1]["metadata"]["snapshot_url"].endswith(".jpg")
    assert not client.QUEUE_FILE.exists()
    assert not list(client.EVIDENCE_QUEUE_DIR.glob("*.jpg"))


def test_offline_queue_retains_jpeg_until_recovery(tmp_path, monkeypatch):
    monkeypatch.setattr(client, "QUEUE_FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(client, "EVIDENCE_QUEUE_DIR", tmp_path / "jpg")
    monkeypatch.setattr(client, "_upload_snapshot",
                        lambda *_: (_ for _ in ()).throw(URLError("offline")))
    posted = []
    monkeypatch.setattr(client, "_post", lambda event: posted.append(deepcopy(event)))
    client.send_event(_event(), b"test-jpeg")
    assert client.QUEUE_FILE.exists()
    assert list(client.EVIDENCE_QUEUE_DIR.glob("*.jpg"))
    assert not posted

    monkeypatch.setattr(client, "_upload_snapshot",
                        lambda event_id, data: f"/api/snapshots/{event_id}.jpg")
    client.flush_pending()
    assert len(posted) == 1
    assert posted[0]["metadata"]["snapshot_status"] == "available"
    assert not client.QUEUE_FILE.exists()
    assert not list(client.EVIDENCE_QUEUE_DIR.glob("*.jpg"))


def test_no_image_reports_unavailability(tmp_path, monkeypatch):
    monkeypatch.setattr(client, "QUEUE_FILE", tmp_path / "events.jsonl")
    monkeypatch.setattr(client, "EVIDENCE_QUEUE_DIR", tmp_path / "jpg")
    posted = []
    monkeypatch.setattr(client, "_post", lambda event: posted.append(event))
    client.send_event(_event())
    assert posted[0]["metadata"]["snapshot_status"] == "capture_unavailable"
    assert "snapshot_url" not in posted[0]["metadata"]
