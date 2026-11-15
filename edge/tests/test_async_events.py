"""No camera, USB device, backend or network required for these tests."""
import threading
import time

from edge.async_events import AsyncEventReporter


def _event(n):
    return {"event_id": str(n), "hazard_type": "zone_entry", "metadata": {}}


def test_submit_is_nonblocking_while_upload_is_stalled():
    entered = threading.Event()
    allow_delivery = threading.Event()
    received = []

    def slow_sender(event, snapshot_jpeg=None):
        entered.set()
        assert allow_delivery.wait(2.0)
        received.append((event["event_id"], snapshot_jpeg))

    worker = AsyncEventReporter(sender=slow_sender, flusher=lambda: None,
                                capacity=4)
    try:
        assert worker.submit(_event(1), b"first")
        assert entered.wait(1.0)
        start = time.perf_counter()
        assert worker.submit(_event(2), b"second")
        assert (time.perf_counter() - start) < 0.05
    finally:
        allow_delivery.set()
        assert worker.close(timeout=2.0)
    assert received == [("1", b"first"), ("2", b"second")]


def test_bounded_backpressure_is_reported_instead_of_blocking():
    entered = threading.Event()
    release = threading.Event()
    received = []

    def slow_sender(event, snapshot_jpeg=None):
        entered.set()
        release.wait(2)
        received.append(event["event_id"])

    worker = AsyncEventReporter(sender=slow_sender, flusher=lambda: None,
                                capacity=1)
    try:
        assert worker.submit(_event(1))
        assert entered.wait(1)
        assert worker.submit(_event(2))
        start = time.perf_counter()
        assert not worker.submit(_event(3))
        assert time.perf_counter() - start < 0.05
    finally:
        release.set()
        assert worker.close(timeout=2)
    assert received == ["1", "2"]


def test_idle_worker_attempts_pending_recovery():
    flushed = threading.Event()
    worker = AsyncEventReporter(sender=lambda *a, **k: None,
                                flusher=flushed.set, retry_seconds=0.1)
    try:
        assert flushed.wait(1)
    finally:
        assert worker.close(timeout=2)


def test_reject_submit_after_shutdown():
    worker = AsyncEventReporter(sender=lambda *a, **k: None,
                                flusher=lambda: None)
    assert worker.close(timeout=2)
    assert worker.submit(_event(1)) is False
