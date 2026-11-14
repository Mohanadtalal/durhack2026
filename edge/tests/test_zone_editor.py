"""Tests for polygon-zone editing without USB hardware or OpenCV."""
import json
import pytest

from edge.zone_editor import (
    DEFAULT_ZONE, ZoneEditor, load_zone, pixels_from_normalized,
    point_in_polygon, person_in_polygon, validate_polygon,
)


def test_default_zone_and_pixel_projection(tmp_path):
    editor = ZoneEditor(tmp_path / "no_file.json")
    assert editor.points == list(DEFAULT_ZONE)
    assert editor.pixels(320, 240) == [(112, 48), (256, 48), (256, 216), (112, 216)]


def test_polygon_including_edge_and_concave_notch():
    # A U-shaped region; centre of the notch is outside.
    poly = [(0, 0), (10, 0), (10, 10), (7, 10), (7, 3), (3, 3), (3, 10), (0, 10)]
    assert point_in_polygon((1, 8), poly)
    assert point_in_polygon((7, 3), poly)
    assert not point_in_polygon((5, 8), poly)
    assert not point_in_polygon((11, 1), poly)
    assert person_in_polygon([(0, 0, 2, 8)], poly)
    assert not person_in_polygon([(4, 3, 6, 8)], poly)


def test_editor_save_reloads_and_reset(tmp_path):
    path = tmp_path / "zones" / "nicla_zone.json"
    editor = ZoneEditor(path)
    editor.begin()
    for x, y in [(20, 20), (240, 20), (240, 180), (20, 180)]:
        editor.add_corner(x, y, 320, 240)
    assert editor.save()
    assert path.exists()
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["version"] == 1
    assert editor.pixels(320, 240) == [(20, 20), (240, 20), (240, 180), (20, 180)]
    assert ZoneEditor(path).pixels(320, 240) == editor.pixels(320, 240)
    assert ZoneEditor(path).pixels(640, 480) == [(40, 40), (480, 40), (480, 360), (40, 360)]
    editor.reset()
    assert not path.exists()
    assert editor.points == list(DEFAULT_ZONE)


def test_undo_and_cancel_preserve_saved_zone(tmp_path):
    editor = ZoneEditor(tmp_path / "zone.json")
    original = editor.pixels(320, 240)
    editor.begin()
    editor.add_corner(10, 20, 320, 240)
    editor.add_corner(20, 30, 320, 240)
    editor.undo()
    assert len(editor.draft) == 1
    editor.cancel()
    assert editor.pixels(320, 240) == original
    assert not editor.path.exists()


def test_reject_small_self_intersecting_and_invalid_zones(tmp_path):
    with pytest.raises(ValueError):
        validate_polygon([(0, 0), (1, 1)])
    with pytest.raises(ValueError):
        validate_polygon([(0, 0), (1, 1), (0, 1), (1, 0)])
    with pytest.raises(ValueError):
        validate_polygon([(0, 0), (0, 0), (1, 0)])
    with pytest.raises(ValueError):
        validate_polygon([(0, 0), (1.2, 0), (0, 1)])
    editor = ZoneEditor(tmp_path / "zone.json")
    editor.begin()
    editor.add_corner(10, 10, 320, 240)
    with pytest.raises(ValueError):
        editor.save()
    assert editor.editing
    assert not editor.path.exists()


def test_corrupted_file_falls_back_to_default(tmp_path):
    path = tmp_path / "zone.json"
    path.write_text("{not json", encoding="utf-8")
    assert load_zone(path) == list(DEFAULT_ZONE)
    path.write_text(json.dumps({"version": 100, "points": []}), encoding="utf-8")
    assert load_zone(path) == list(DEFAULT_ZONE)
