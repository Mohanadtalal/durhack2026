"""UNO Q Linux-side probe: verify Nicla MJPEG frames really arrive over Wi-Fi.

This does not perform AI inference; it only confirms the camera-to-board link.
Install/run through UNO Q ADB shell (uses Python standard library only).
"""
import sys
from urllib.request import urlopen


def read_first_jpeg(stream, max_bytes=2_000_000):
    """Extract JPEG SOI..EOI from an MJPEG stream without saving footage."""
    received = bytearray()
    total_received = 0
    while total_received < max_bytes:
        chunk = stream.read(min(4096, max_bytes - total_received))
        if not chunk:
            raise ConnectionError("Camera stream ended before a complete JPEG frame")
        total_received += len(chunk)
        received.extend(chunk)
        start = received.find(b"\xff\xd8")
        if start < 0:
            if len(received) > 8192:
                del received[:-2]
            continue
        end = received.find(b"\xff\xd9", start + 2)
        if end >= 0:
            return bytes(received[start:end + 2])
        if start:
            del received[:start]
    raise ValueError("Received frame exceeds size limit")


def main():
    if len(sys.argv) != 2:
        print("Usage: python3 check_wifi_camera.py http://NICLA_IP:8080/stream.mjpg")
        raise SystemExit(2)
    url = sys.argv[1]
    if not url.startswith("http://") or not url.endswith("/stream.mjpg"):
        raise SystemExit("Expected a local Nicla HTTP MJPEG /stream.mjpg URL")
    with urlopen(url, timeout=8) as response:
        kind = response.headers.get("Content-Type", "").lower()
        if "multipart/x-mixed-replace" not in kind:
            raise ValueError("Not an MJPEG stream: " + kind)
        frame = read_first_jpeg(response)
    print("UNO Q RECEIVED Nicla Wi-Fi camera JPEG:", len(frame), "bytes")
    print("Camera-to-Arduino Wi-Fi transport is working; AI inference not yet enabled.")


if __name__ == "__main__":
    main()
