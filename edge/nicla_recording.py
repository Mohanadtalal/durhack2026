"""Synchronize fixed-FPS MP4 output to real Nicla camera timestamps.

When the camera is slower than the output FPS, repeat the previous annotated
frame. When faster, skip intermediate captures. USB outages are excluded.
This does not interpolate motion or improve the model inference frame rate.
"""
import math


class TimedFrameRecorder:
    def __init__(self, writer, fps=10.0, max_gap_seconds=2.0):
        if not math.isfinite(fps) or fps <= 0:
            raise ValueError("FPS must be positive and finite")
        if not math.isfinite(max_gap_seconds) or max_gap_seconds < 1 / fps:
            raise ValueError("Maximum gap must be at least one frame interval")
        self.writer = writer
        self.fps = float(fps)
        self.max_gap_seconds = float(max_gap_seconds)
        self.frames_written = 0
        self._start = None
        self._previous_time = None
        self._last_frame = None
        self._paused_at = None

    @property
    def duration_seconds(self):
        return self.frames_written / self.fps

    def pause(self, at):
        """Exclude the USB-disconnected interval from the output video."""
        if not math.isfinite(at):
            raise ValueError("Invalid timestamp")
        if self._start is not None and self._paused_at is None:
            self._paused_at = max(at, self._previous_time)

    def write(self, frame, at):
        if not math.isfinite(at):
            raise ValueError("Invalid timestamp")
        if self._start is None:
            self._start = at
        elif at < self._previous_time:
            raise ValueError("Frame timestamps must not go backwards")
        elif self._paused_at is not None:
            self._start += max(0.0, at - self._paused_at)
            self._paused_at = None
        elif at - self._previous_time > self.max_gap_seconds:
            # Limit frozen footage after unexpected long capture stalls.
            self._start += at - self._previous_time - self.max_gap_seconds

        elapsed = max(0.0, at - self._start)
        required = math.floor(elapsed * self.fps + 1e-8) + 1
        if required > self.frames_written:
            while self.frames_written < required - 1:
                self.writer.write(self._last_frame)
                self.frames_written += 1
            self.writer.write(frame)
            self.frames_written += 1

        # Keep previous frame independently in case caller reuses array.
        self._last_frame = frame.copy() if hasattr(frame, "copy") else frame
        self._previous_time = at

    def release(self):
        self.writer.release()
