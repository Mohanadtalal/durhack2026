"""Optional, localhost-only Arduino UNO Q warning display bridge.

The Nicla detector owns hazard decisions; this worker mirrors their latest state
to a UNO Q App Lab Web UI endpoint over an ADB-forwarded HTTP port.

This is an advisory hackathon display, NOT a safety-rated alarm. No authentication
or transport security is provided; only loopback URLs are allowed.
"""
import threading
import time
from urllib.parse import urlsplit
from urllib.request import Request, urlopen


class UnoQWarning:
    """Retry and periodically re-send the newest warning state off the camera thread."""

    def __init__(self, base_url: str, *, timeout: float = 0.5,
                 sync_interval: float = 2.0, retry_interval: float = 1.0):
        parsed = urlsplit(base_url.strip())
        if (parsed.scheme != "http"
                or parsed.hostname not in {"localhost", "127.0.0.1", "::1"}
                or parsed.username or parsed.password
                or parsed.path not in ("", "/")
                or parsed.query or parsed.fragment):
            raise ValueError(
                "UNO Q URL must be a local HTTP endpoint, e.g. "
                "http://127.0.0.1:7000 (ADB port forwarding required)."
            )
        if not parsed.port:
            raise ValueError("UNO Q URL must include a port, e.g. :7000.")
        if min(timeout, sync_interval, retry_interval) <= 0:
            raise ValueError("UNO Q timeouts and intervals must be positive.")

        self.base_url = base_url.strip().rstrip("/")
        self.timeout = timeout
        self.sync_interval = sync_interval
        self.retry_interval = retry_interval
        self._condition = threading.Condition()
        self._desired = False
        self._revision = 0
        self._stopping = False
        self._thread = threading.Thread(
            target=self._worker, name="uno-q-warning", daemon=True
        )
        self._thread.start()

    def set_state(self, active: bool) -> None:
        """Never wait for HTTP in the camera / detection thread."""
        with self._condition:
            if self._stopping:
                return
            value = bool(active)
            if value != self._desired:
                self._desired = value
                self._revision += 1
                self._condition.notify_all()

    def _send(self, active: bool) -> None:
        path = "/danger/on" if active else "/danger/off"
        request = Request(self.base_url + path, method="POST")
        with urlopen(request, timeout=self.timeout) as response:
            # HTTPError is raised for non-2xx responses by urllib.
            response.read(1)

    def _worker(self) -> None:
        ack_revision = -1  # Ensure an OFF sync happens at startup.
        last_success = 0.0
        next_attempt = 0.0
        was_unreachable = False
        last_error_log = 0.0

        while True:
            with self._condition:
                while True:
                    if self._stopping:
                        return
                    now = time.monotonic()
                    due = max(next_attempt,
                              0.0 if ack_revision != self._revision
                              else last_success + self.sync_interval)
                    if now >= due:
                        desired, revision = self._desired, self._revision
                        break
                    self._condition.wait(timeout=due - now)

            try:
                self._send(desired)
            except (OSError, TimeoutError, ValueError) as exc:
                now = time.monotonic()
                if not was_unreachable or now - last_error_log >= 15:
                    print(f"[UNO Q] Display unreachable; retrying: {type(exc).__name__}: {exc}")
                    last_error_log = now
                was_unreachable = True
                next_attempt = now + self.retry_interval
                continue

            now = time.monotonic()
            with self._condition:
                if revision == self._revision:
                    ack_revision = revision
            if was_unreachable or last_success == 0 or revision != ack_revision:
                print("[UNO Q] Connected; warning state synchronised")
            was_unreachable = False
            last_success = now
            next_attempt = now
            # Re-send even when unchanged: recovers after UNO Q App Lab restarts.

    def close(self) -> None:
        """Stop the worker, then attempt one bounded, final display-clear request."""
        with self._condition:
            if self._stopping:
                return
            self._stopping = True
            self._condition.notify_all()
        self._thread.join(timeout=self.timeout + 1.0)
        if self._thread.is_alive():
            print("[UNO Q] Worker did not stop; display state is unconfirmed")
            return  # Avoid racing a late ON request with a final OFF.
        try:
            self._send(False)
        except (OSError, TimeoutError, ValueError):
            print("[UNO Q] Could not clear display at shutdown; check board manually")
