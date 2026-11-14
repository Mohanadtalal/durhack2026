"""Video test helper can be imported and validated without OpenCV or GPU."""
import pytest

from edge.nicla_video_test import frame_step, main, run


def test_frame_sampling_selects_valid_steps():
    assert frame_step(60.0, 8.0) == 8
    assert frame_step(30.0, 8.0) == 4
    assert frame_step(6.0, 8.0) == 1
    assert frame_step(0, 8.0) == 4


def test_video_helper_entrypoints():
    assert callable(main)
    assert callable(run)


def test_invalid_sample_fps():
    for val in (0, -1, float("inf"), float("nan")):
        with pytest.raises(ValueError):
            frame_step(60.0, val)
