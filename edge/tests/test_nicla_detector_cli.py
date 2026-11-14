"""Smoke test: detector CLI is importable without a camera or ML runtime."""
from edge.nicla_detector import main, run


def test_detector_entrypoints_available():
    assert callable(main)
    assert callable(run)
