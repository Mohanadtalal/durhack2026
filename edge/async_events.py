"""Off-camera-thread incident dispatch for responsive Nicla video.

The camera's capture/inference loop must never perform HTTP requests.
The background worker uses the existing client.send_event() disk-backed retry
queue, including its snapshot-first upload ordering.

New events are briefly held in a bounded memory queue. On abrupt process
termination, items not yet picked up by the worker can be lost; this remains
prototype monitoring software, not a certified incident recorder.
"""
import queue
import threading

from .client import flush_pending, send_event


class AsyncEventReporter:
    def __init__(self, *, sender=None, flusher=None, capacity=256,
                 retry_seconds=5.0):
        if capacity < 1 or retry_seconds <= 0:
            raise ValueError("Invalid event reporter queue configuration")
        self._sender = sender if sender is not None else send_event
        self._flusher = flusher if flusher is not None else flush_pending
        self._pending = queue.Queue(maxsize=capacity)
        self._closed = False
        self._retry_seconds = float(retry_seconds)
        self._thread = threading.Thread(
            target=self._work, name="siteguardian-event-delivery", daemon=True,
        )
        self._thread.start()

    def submit(self, event: dict, snapshot_jpeg: bytes | None = None) -> bool:
        """Return instantly; never wait for MongoDB/HTTP/snapshot storage.

        False means the queue is full or the reporter is closing; callers
        should announce that this event wasn't recorded.
        """
        if self._closed:
            return False
        try:
            self._pending.put_nowait((event, snapshot_jpeg))
        except queue.Full:
            return False
        return True

    def _flush(self):
        try:
            self._flusher()
        except Exception as exc:
            print("[EVENT WORKER] Could not flush older incidents:", exc)

    def _work(self):
        # All queue file and HTTP operations happen on this single thread.
        self._flush()
        while True:
            if self._closed and self._pending.empty():
                return
            try:
                event, image = self._pending.get(timeout=min(0.25, self._retry_seconds))
            except queue.Empty:
                if not self._closed:
                    self._flush()
                continue
            try:
                self._sender(event, snapshot_jpeg=image)
            except Exception as exc:
                # Keep worker alive; delivery itself handles retriable network
                # errors and persists them. This indicates an unexpected failure.
                print("[EVENT WORKER] Unexpected incident delivery error:", exc)
            finally:
                self._pending.task_done()

    def close(self, timeout=12.0) -> bool:
        """Drain queued events when possible. Return False on shutdown timeout."""
        self._closed = True
        self._thread.join(timeout=timeout)
        if self._thread.is_alive():
            print("[EVENT WORKER] Still delivering: shutdown may lose buffered events.")
            return False
        return True
