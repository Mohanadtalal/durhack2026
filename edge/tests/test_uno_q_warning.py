"""UNO Q warning bridge tests; never require real hardware or network."""
import io
import time

import pytest

from edge import uno_q_warning
from edge.uno_q_warning import UnoQWarning


def wait_until(predicate, timeout=2.0):
    deadline = time.monotonic() + timeout
    while time.monotonic() < deadline:
        if predicate():
            return
        time.sleep(0.01)
    assert predicate(), "Warning command was not sent before the test deadline"


def test_on_off_and_periodic_resync(monkeypatch):
    sent = []

    def fake_open(request, timeout):
        assert request.get_method() == "POST"
        assert timeout == 0.05
        sent.append(request.full_url.rsplit("/", 1)[-1])
        return io.BytesIO(b"{}")

    monkeypatch.setattr(uno_q_warning, "urlopen", fake_open)
    display = UnoQWarning(
        "http://127.0.0.1:7000",
        timeout=0.05, sync_interval=0.07, retry_interval=0.02,
    )
    try:
        wait_until(lambda: sent.count("off") >= 1)  # Startup clears stale warning.
        display.set_state(True)
        wait_until(lambda: sent.count("on") >= 1)
        wait_until(lambda: sent.count("on") >= 2)  # State survives UNO Q reboot.
        display.set_state(False)
        wait_until(lambda: sent[-1] == "off")
    finally:
        display.close()
    assert sent[-1] == "off"  # Best-effort shutdown clears warning.


def test_retries_when_uno_q_app_starts_late(monkeypatch):
    attempts = []
    ready = False

    def fake_open(request, timeout):
        attempts.append(request.full_url)
        if not ready:
            raise ConnectionRefusedError("UNO Q App Lab stopped")
        return io.BytesIO(b"ok")

    monkeypatch.setattr(uno_q_warning, "urlopen", fake_open)
    display = UnoQWarning(
        "http://localhost:7000",
        timeout=0.05, sync_interval=0.06, retry_interval=0.02,
    )
    try:
        display.set_state(True)
        wait_until(lambda: len(attempts) >= 2)
        ready = True
        wait_until(lambda: len(attempts) >= 3)
        wait_until(lambda: sum(x.endswith("/on") for x in attempts) >= 3)
        assert display._thread.is_alive()
    finally:
        display.close()


def test_set_state_never_blocks_on_http(monkeypatch):
    def slow_open(request, timeout):
        time.sleep(0.15)
        return io.BytesIO(b"")

    monkeypatch.setattr(uno_q_warning, "urlopen", slow_open)
    display = UnoQWarning("http://127.0.0.1:7000", timeout=0.05)
    try:
        start = time.monotonic()
        display.set_state(True)
        elapsed = time.monotonic() - start
        assert elapsed < 0.05
    finally:
        display.close()


@pytest.mark.parametrize("url", [
    "https://127.0.0.1:7000",
    "http://192.168.1.20:7000",
    "http://127.0.0.1:7000/other",
    "http://user:pass@127.0.0.1:7000",
    "http://127.0.0.1",
])
def test_rejects_non_local_or_incorrect_url(url):
    with pytest.raises(ValueError):
        UnoQWarning(url)
