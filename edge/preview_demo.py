"""Safe local HTTP preview fixture for full-stack browser checks.

Runs the real preview server with a *synthetic image*, not Nicla hardware.
Never reports the mock image as real detection. Stdlib + Pillow for CI only.
"""
from io import BytesIO
import time
from PIL import Image, ImageDraw
from edge.preview_server import PreviewServer


def main():
    server = PreviewServer("127.0.0.1", 8765)
    server.update_zones([{
        "id": "nicla-zone-1",
        "label": "Restricted zone 1",
        "points": [[0.15, 0.20], [0.85, 0.20], [0.85, 0.80], [0.15, 0.80]],
    }])
    image = Image.new("RGB", (320, 240), "#123454")
    draw = ImageDraw.Draw(image)
    draw.rectangle((48, 48, 272, 192), outline="#eecc55", width=3)
    draw.text((55, 54), "SIMULATED CAMERA TEST", fill="#ffffff")
    buf = BytesIO()
    image.save(buf, format="JPEG", quality=70)
    payload = buf.getvalue()
    print("[MOCK CAMERA] Test frames on http://127.0.0.1:8765/stream.mjpg", flush=True)
    try:
        while True:
            server.hub.publish(payload)
            time.sleep(0.25)
    except KeyboardInterrupt:
        pass
    finally:
        server.close()


if __name__ == "__main__":
    main()
