from edge.zone_rules import ZoneMonitor

def test_entry_dwell_one_each():
    monitor = ZoneMonitor(dwell_seconds=4)
    assert monitor.update(False, 0) == []
    assert monitor.update(True, 1) == ["zone_entry"]
    assert monitor.update(True, 2) == []
    assert monitor.update(True, 5) == ["prolonged_exposure"]
    assert monitor.update(True, 20) == []

def test_reset_on_exit_and_reentry():
    monitor = ZoneMonitor(dwell_seconds=3)
    assert monitor.update(True, 0) == ["zone_entry"]
    assert monitor.update(False, 2) == []
    assert monitor.update(True, 4) == ["zone_entry"]
    assert monitor.update(True, 7) == ["prolonged_exposure"]
