"""Real HTTP tests; run without camera, OpenCV or Ultralytics."""
import json
import time
from urllib.error import HTTPError
from urllib.request import urlopen

from edge.preview_server import FrameHub, PreviewServer, zones_for_editor


class FakeEditor:
    zones = [
        [(0.1, 0.2), (0.8, 0.2), (0.5, 0.9)],
        [(0.1, 0.3), (0.3, 0.3), (0.2, 0.6)],
    ]


def test_zone_ids_align_with_emitted_edge_incidents():
    result = zones_for_editor(FakeEditor(), sharp_zone_ids={2})
    assert [zone["id"] for zone in result] == ["nicla-zone-1", "nicla-zone-2"]
    assert result[1]["label"] == "Marked sharp zone 2"
    assert result[0]["points"][0] == [0.1, 0.2]


def test_live_server_status_snapshot_and_refresh_without_hardware():
    server = PreviewServer("127.0.0.1", 0)
    base = "http://127.0.0.1:" + str(server.address[1])
    try:
        with urlopen(base + "/status.json", timeout=3) as r:
            initial = json.load(r)
            assert r.status == 200
        assert initial["connected"] is False
        assert initial["last_frame_age_seconds"] is None
        assert initial["zones"] == []

        server.update_zones(zones_for_editor(FakeEditor()))
        # JPEG magic bytes are sufficient for the HTTP transport test.
        raw = b"\xff\xd8" + b"faked-bytes" + b"\xff\xd9"
        server.hub.publish(raw)
        with urlopen(base + "/snapshot.jpg", timeout=3) as r:
            assert r.headers.get_content_type() == "image/jpeg"
            assert r.read() == raw
        with urlopen(base + "/status.json", timeout=3) as r:
            state = json.load(r)
        assert state["connected"] is True
        assert len(state["zones"]) == 2
        assert state["zones"][0]["id"] == "nicla-zone-1"
        assert state["last_frame_age_seconds"] is not None

        # If frames stop, say monitoring is disconnected, not "all clear".
        with server.hub.condition:
            server.hub.last_frame = time.monotonic() - 10
        with urlopen(base + "/status.json", timeout=3) as r:
            assert json.load(r)["connected"] is False
        try:
            urlopen(base + "/snapshot.jpg", timeout=3)
            assert False, "An outdated image must not be served as live"
        except HTTPError as e:
            assert e.code == 503
    finally:
        server.close()


def test_mjpeg_sends_multipart_frame():
    server = PreviewServer("127.0.0.1", 0)
    base = "http://127.0.0.1:" + str(server.address[1])
    try:
        image = b"\xff\xd8demo\xff\xd9"
        server.hub.publish(image)
        with urlopen(base + "/stream.mjpg", timeout=4) as response:
            assert response.headers.get_content_type() == "multipart/x-mixed-replace"
            header = response.readline()
            assert header == b"--frame\r\n"
            assert response.readline() == b"Content-Type: image/jpeg\r\n"
            assert response.readline().startswith(b"Content-Length:")
            assert response.readline() == b"\r\n"
            assert response.read(len(image)) == image
    finally:
        server.close()


def test_hub_rejects_unbounded_image():
    hub = FrameHub()
    try:
        hub.publish(b"x" * 2_000_001)
        assert False
    except ValueError:
        pass
