import pytest
from edge.nicla_extra_rules import (
    ProximityAlert, extract_ppe_hazards, ppe_hazard_from_label, supported_ppe_classes,
)


def test_missing_ppe_requires_explicit_label():
    names = {0: "person", 1: "helmet", 2: "no_helmet", 3: "no_vest"}
    assert supported_ppe_classes(names) == {"missing_helmet", "missing_vest"}
    rows = [(0, .95, [0, 0, 10, 10]), (1, .90, [1, 1, 5, 5]),
            (2, .88, [3, 3, 6, 6]), (3, .20, [4, 4, 9, 9])]
    assert extract_ppe_hazards(names, rows) == [("missing_helmet", (3, 3, 6, 6), .88)]
    assert supported_ppe_classes(["person", "safety vest", "helmet"]) == set()
    assert ppe_hazard_from_label("No-Hard-Hat") == "missing_helmet"


def test_proximity_debounce_and_invalid():
    alert = ProximityAlert(800)
    assert alert.update(500) == (False, False)
    assert alert.update(400) == (True, False)
    assert alert.near
    assert alert.update(None) == (False, False)
    assert alert.near
    assert alert.update(1200) == (False, False)
    assert alert.update(1300) == (False, True)
    assert not alert.near
    with pytest.raises(ValueError):
        ProximityAlert(20)
    with pytest.raises(ValueError):
        ProximityAlert(900, 0)
