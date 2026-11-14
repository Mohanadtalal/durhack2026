import pytest
from edge.nicla_geometry import DebouncedOccupancy, person_in_zone, zone_from_fractions

def test_geometry():
    zone = zone_from_fractions(320,240)
    assert zone == (112,48,256,216)
    assert person_in_zone([(130,80,155,200)],zone)
    assert not person_in_zone([(0,0,60,60)],zone)

def test_invalid_bounds():
    with pytest.raises(ValueError):
        zone_from_fractions(320,240,.8,.1,.4,.9)

def test_debouncing():
    d = DebouncedOccupancy(2)
    assert not d.update(True)
    assert d.update(True)
    assert d.update(False)
    assert not d.update(False)
