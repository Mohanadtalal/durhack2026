"""Loopback-only HTTP preview of the *annotated* Nicla camera image.

This server is a local hackathon diagnostic interface, NOT an authenticated
production video service. It starts only with --stream-port and binds to
127.0.0.1 unless the operator explicitly overrides --stream-host.

GET /stream.mjpg   multipart MJPEG of recent annotated camera frames
GET /snapshot.jpg  last frame, HTTP 503 if no recent frame
GET /status.json   whether a new frame arrived within five seconds, plus
                   the real normalized zone polygons from ZoneEditor
"""
import json
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import urlsplit

FRAME_STALE_AFTER = 5.0
ALLOWED_ORIGINS = {"http://127.0.0.1:5173", "http://localhost:5173"}


def zones_for_editor(editor, sharp_zone_ids=()):
    """Return names and actual normalized geometry matching emitted incident IDs."""
    sharp = set(sharp_zone_ids)
    return [
        {
            "id": f"nicla-zone-{i}",
            "label": (f"Marked sharp zone {i}" if i in sharp else f"Restricted zone {i}"),
            "points": [[round(x, 6), round(y, 6)] for x, y in polygon],
        }
        for i, polygon in enumerate(editor.zones, start=1)
    ]


class FrameHub:
    def __init__(self):
        self.condition = threading.Condition()
        self.jpeg = None
        self.sequence = 0
        self.last_frame = None
        self.zones = []
        self.closed = False

    def publish(self, jpeg):
        if not jpeg or not isinstance(jpeg, bytes) or len(jpeg) > 2_000_000:
            raise ValueError("Expected bounded JPEG bytes")
        with self.condition:
            self.jpeg = jpeg
            self.last_frame = time.monotonic()
            self.sequence += 1
            self.condition.notify_all()

    def update_zones(self, zones):
        with self.condition:
            self.zones = list(zones)

    def status(self):
        with self.condition:
            age = None if self.last_frame is None else max(
                0, time.monotonic() - self.last_frame)
            return {
                "source_id": "nicla-vision-01",
                "connected": age is not None and age < FRAME_STALE_AFTER,
                "last_frame_age_seconds": None if age is None else round(age, 1),
                "zones": list(self.zones),
                "prototype": True,
            }

    def snapshot(self):
        with self.condition:
            return self.jpeg, self.last_frame


class _Handler(BaseHTTPRequestHandler):
    protocol_version = "HTTP/1.1"

    def _cors(self):
        origin = self.headers.get("Origin")
        if origin in ALLOWED_ORIGINS:
            self.send_header("Access-Control-Allow-Origin", origin)
            self.send_header("Vary", "Origin")

    def _head(self, code, content_type, length=None):
        self.send_response(code)
        self.send_header("Content-Type", content_type)
        self.send_header("Cache-Control", "no-store, max-age=0")
        self.send_header("X-Content-Type-Options", "nosniff")
        self._cors()
        if length is not None:
            self.send_header("Content-Length", str(length))
        self.end_headers()

    def do_GET(self):
        path = urlsplit(self.path).path
        hub = self.server.frame_hub
        if path == "/status.json":
            body = json.dumps(hub.status()).encode("utf-8")
            self._head(200, "application/json; charset=utf-8", len(body))
            self.wfile.write(body)
            return
        if path == "/snapshot.jpg":
            jpeg, at = hub.snapshot()
            if at is None or time.monotonic() - at > FRAME_STALE_AFTER:
                body = b"Camera has no recent frame"
                self._head(503, "text/plain; charset=utf-8", len(body))
                self.wfile.write(body)
                return
            self._head(200, "image/jpeg", len(jpeg))
            self.wfile.write(jpeg)
            return
        if path == "/stream.mjpg":
            self._head(200, "multipart/x-mixed-replace; boundary=frame")
            last_seq = -1
            try:
                while not hub.closed:
                    with hub.condition:
                        hub.condition.wait_for(
                            lambda: hub.sequence != last_seq or hub.closed,
                            timeout=2)
                        sequence = hub.sequence
                        jpeg = hub.jpeg
                        at = hub.last_frame
                    if sequence == last_seq or jpeg is None or (
                        at is None or time.monotonic() - at > FRAME_STALE_AFTER
                    ):
                        continue
                    last_seq = sequence
                    header = (
                        b"--frame\r\nContent-Type: image/jpeg\r\nContent-Length: "
                        + str(len(jpeg)).encode("ascii") + b"\r\n\r\n"
                    )
                    self.wfile.write(header + jpeg + b"\r\n")
                    self.wfile.flush()
            except (BrokenPipeError, ConnectionResetError, OSError):
                pass
            return
        self._head(404, "text/plain; charset=utf-8", 0)

    def log_message(self, format_string, *args):
        # A poll or each MJPEG frame should not flood the edge terminal.
        return


class PreviewServer:
    """Owns HTTP worker and cached JPEG. All image decoding remains on edge."""

    def __init__(self, host="127.0.0.1", port=8765):
        self.hub = FrameHub()
        self.http = ThreadingHTTPServer((host, port), _Handler)
        self.http.daemon_threads = True
        self.http.frame_hub = self.hub
        self.thread = threading.Thread(
            target=self.http.serve_forever, daemon=True, name="siteguardian-preview")
        self.thread.start()
        self.last_encode = 0.0

    @property
    def address(self):
        return self.http.server_address

    def publish_frame(self, frame):
        # At most ~8 JPEG encodes per second; never hold image data indefinitely
        # on a disconnected client. This is for demo preview, not archival.
        now = time.monotonic()
        if now - self.last_encode < 0.125:
            return
        import cv2
        ok, encoded = cv2.imencode(".jpg", frame, [cv2.IMWRITE_JPEG_QUALITY, 70])
        if ok:
            self.hub.publish(encoded.tobytes())
            self.last_encode = now

    def update_zones(self, zones):
        self.hub.update_zones(zones)

    def close(self):
        with self.hub.condition:
            self.hub.closed = True
            self.hub.condition.notify_all()
        self.http.shutdown()
        self.http.server_close()
        self.thread.join(timeout=3)
