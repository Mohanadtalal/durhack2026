"""Smoke test: detector CLI is importable without a camera or ML runtime."""
from edge.nicla_detector import main, run


def test_detector_entrypoints_available():
    assert callable(main)
    assert callable(run)


def test_cli_accepts_auto_hazards_and_latency_flags_together(monkeypatch):
    """Regression: the exact command used by the operator must be accepted."""
    import sys
    import edge.nicla_detector as detector
    calls = []
    monkeypatch.setattr(detector, "run", lambda *args: calls.append(args))
    monkeypatch.setattr(sys, "argv", [
        "nicla_detector", "--port", "COM9", "--auto-hazards",
        "--hazard-labels", "knife", "--predictive",
        "--stream-port", "8765", "--profile-latency",
    ])
    detector.main()
    assert len(calls) == 1
    args = calls[0]
    assert args[0] == "COM9"
    assert args[10] is True  # prediction on existing person/vehicle tracker
    assert args[15] == 8765
    assert args[18] is True  # frame-stage performance logging
    assert args[19] is True  # automatic hazard detection
    assert args[21] == "knife"
