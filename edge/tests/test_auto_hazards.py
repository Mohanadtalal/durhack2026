"""Pure logic checks for automatic sharp-object recognition and alert lifecycle."""
import pytest

from edge.auto_hazards import HazardMonitor, find_hazards, parse_labels


def test_knife_recognition_follows_model_box_and_track_id():
    rows = [
        (0, 0.86, (10.1, 20, 51, 92), 42),
        (1, 0.99, (70, 80, 120, 130), 7),
        (0, 0.15, (1, 1, 2, 2), None),
    ]
    found = find_hazards({0: "Knife", 1: "person"}, rows,
                         parse_labels("knife"), 0.45)
    assert len(found) == 1
    assert found[0].label == "knife"
    assert found[0].track_id == 42
    assert found[0].box == (10, 20, 51, 92)
    assert found[0].confidence == 0.86


def test_warning_starts_on_first_frame_no_roi_needed():
    monitor = HazardMonitor(clear_after=3)
    knife = find_hazards(["knife"], [(0, .75, (5, 5, 20, 40), None)],
                         ("knife",))
    assert monitor.update(knife) is True
    assert monitor.active is True
    assert monitor.update(knife) is False  # no duplicate incident every frame
    assert monitor.update([]) is False
    assert monitor.active is True  # avoid blinking for one model miss
    assert monitor.update([]) is False
    assert monitor.active is True
    assert monitor.update([]) is False
    assert monitor.active is False
    assert monitor.update(knife) is True  # new episode


def test_monitor_reset_and_independent_instances():
    a, b = HazardMonitor(), HazardMonitor()
    a.update([object()])
    assert a.active and not b.active
    a.reset()
    assert not a.active and a.missed == 0


def test_labels_must_be_nonempty_and_exact():
    assert parse_labels(" knife , saw, KNIFE ") == ("knife", "saw")
    with pytest.raises(ValueError):
        parse_labels(" , , ")
    assert not find_hazards({0: "butter knife"}, [(0, .99, (1, 2, 3, 4), 1)],
                            ("knife",))
    with pytest.raises(ValueError):
        find_hazards(["knife"], [], ("knife",), 0)
