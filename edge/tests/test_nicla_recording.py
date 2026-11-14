"""Timing tests without needing OpenCV, NumPy or camera hardware."""
import pytest
from edge.nicla_recording import TimedFrameRecorder


class WriterStub:
    def __init__(self):
        self.frames = []
        self.closed = False

    def write(self, frame):
        self.frames.append(frame)

    def release(self):
        self.closed = True


def test_slow_capture_keeps_elapsed_time():
    writer = WriterStub()
    recording = TimedFrameRecorder(writer, fps=10)
    for i, when in enumerate([0.0, 0.25, 0.50, 0.75, 1.0]):
        recording.write(str(i), when)
    assert recording.frames_written == 11
    assert recording.duration_seconds == pytest.approx(1.1)
    assert writer.frames[0] == "0"
    assert writer.frames[1] == "0"
    assert writer.frames[2] == "1"
    assert writer.frames[-1] == "4"
    recording.release()
    assert writer.closed


def test_fast_capture_drops_extra_input_frames():
    writer = WriterStub()
    recording = TimedFrameRecorder(writer, fps=10)
    for i, when in enumerate([0.0, 0.02, 0.04, 0.11, 0.15, 0.20]):
        recording.write(str(i), when)
    assert writer.frames == ["0", "3", "5"]


def test_usb_outage_is_not_recorded_as_long_frozen_gap():
    writer = WriterStub()
    recording = TimedFrameRecorder(writer, fps=10)
    recording.write("before", 0.0)
    recording.write("before2", 0.2)
    recording.pause(0.25)
    recording.write("after", 40.25)
    assert writer.frames == ["before", "before", "before2", "after"]


def test_unexpected_stall_is_capped_at_two_seconds():
    writer = WriterStub()
    recording = TimedFrameRecorder(writer, fps=10, max_gap_seconds=2.0)
    recording.write("before", 0.0)
    recording.write("after", 100.0)
    assert recording.frames_written == 21


def test_bad_parameters_or_timestamps():
    for fps in [0, -1, float("nan")]:
        with pytest.raises(ValueError):
            TimedFrameRecorder(WriterStub(), fps=fps)
    with pytest.raises(ValueError):
        TimedFrameRecorder(WriterStub(), fps=10, max_gap_seconds=0.05)
    recording = TimedFrameRecorder(WriterStub())
    recording.write("first", 2.0)
    with pytest.raises(ValueError):
        recording.write("old", 1.0)
    with pytest.raises(ValueError):
        recording.write("bad", float("inf"))
