"""No-hardware test of the UNO Q's MJPEG connectivity probe."""
import importlib.util
import io
from pathlib import Path

import pytest


file_path = (Path(__file__).resolve().parents[2] / "hardware" /
             "uno_q_warning" / "python" / "check_wifi_camera.py")
spec = importlib.util.spec_from_file_location("check_wifi_camera", file_path)
probe = importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)


def test_first_jpeg_from_mjpeg_stream():
    fake = io.BytesIO(
        b"--frame\r\nContent-Type: image/jpeg\r\n\r\n"
        b"\xff\xd8SAMPLEJPEG\xff\xd9\r\n--frame"
    )
    assert probe.read_first_jpeg(fake) == b"\xff\xd8SAMPLEJPEG\xff\xd9"


def test_frame_read_rejects_invalid_stream():
    with pytest.raises(ConnectionError):
        probe.read_first_jpeg(io.BytesIO(b"--frame without jpeg"))
    with pytest.raises(ValueError):
        probe.read_first_jpeg(io.BytesIO(b"\xff\xd8" + b"x" * 200),
                              max_bytes=100)
