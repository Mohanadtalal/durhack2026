"""Tests for multiple Nicla polygon zones; no hardware or OpenCV needed."""
import json
import pytest

from edge.zone_editor import (
    DEFAULT_ZONE_FILE, MAX_ZONES, ZoneEditor, load_zones,
    point_in_polygon, person_in_polygon, validate_polygon,
)


def draw(editor, points):
    editor.begin()
    for x, y in points:
        editor.add_corner(x, y, 320, 240)
    assert editor.save()


def test_empty_by_default_and_new_file_name(tmp_path):
    editor = ZoneEditor(tmp_path / "does_not_exist.json")
    assert editor.zones == []
    assert editor.pixels(320, 240) == []
    assert DEFAULT_ZONE_FILE.name == "nicla_zones.json"


def test_two_additive_zones_persist_and_reset(tmp_path):
    path = tmp_path / "zones" / "nicla_zones.json"
    editor = ZoneEditor(path)
    first = [(20, 20), (100, 20), (100, 130), (20, 130)]
    second = [(175, 30), (270, 30), (270, 170), (175, 170)]
    draw(editor, first)
    assert len(editor.zones) == 1
    draw(editor, second)
    assert len(editor.zones) == 2
    expected = [first, second]
    assert editor.pixels(320, 240) == expected
    assert ZoneEditor(path).pixels(320, 240) == expected
    assert ZoneEditor(path).pixels(640, 480) == [
        [(x * 2, y * 2) for x, y in region] for region in expected
    ]
    payload = json.loads(path.read_text(encoding="utf-8"))
    assert payload["version"] == 2
    assert len(payload["zones"]) == 2
    assert person_in_polygon([(35, 10, 55, 100)], editor.pixels(320, 240)[0])
    assert not person_in_polygon([(35, 10, 55, 100)], editor.pixels(320, 240)[1])
    assert person_in_polygon([(190, 10, 210, 100)], editor.pixels(320, 240)[1])
    editor.reset()
    assert editor.zones == []
    assert not path.exists()
    assert ZoneEditor(path).zones == []


def test_polygon_edges_concave_and_outside():
    poly = [(0, 0), (10, 0), (10, 10), (7, 10), (7, 3), (3, 3), (3, 10), (0, 10)]
    assert point_in_polygon((1, 8), poly)
    assert point_in_polygon((7, 3), poly)
    assert not point_in_polygon((5, 8), poly)
    assert not point_in_polygon((11, 1), poly)


def test_cancel_undo_does_not_remove_previous_zone(tmp_path):
    editor = ZoneEditor(tmp_path / "nicla_zones.json")
    draw(editor, [(20, 20), (100, 20), (100, 130), (20, 130)])
    prior = editor.pixels(320, 240)
    editor.begin()
    editor.add_corner(10, 20, 320, 240)
    editor.add_corner(20, 30, 320, 240)
    editor.undo()
    assert len(editor.draft) == 1
    editor.cancel()
    assert editor.pixels(320, 240) == prior
    assert len(ZoneEditor(editor.path).zones) == 1


def test_invalid_polygon_does_not_replace_existing_zones(tmp_path):
    path = tmp_path / "nicla_zones.json"
    editor = ZoneEditor(path)
    draw(editor, [(20, 20), (100, 20), (100, 130), (20, 130)])
    prior = path.read_text(encoding="utf-8")
    for points in [
        [(0, 0), (1, 1)],
        [(0, 0), (1, 1), (0, 1), (1, 0)],
        [(0, 0), (0, 0), (1, 0)],
        [(0, 0), (1.2, 0), (0, 1)],
    ]:
        with pytest.raises(ValueError):
            validate_polygon(points)
    editor.begin()
    editor.add_corner(10, 10, 320, 240)
    with pytest.raises(ValueError):
        editor.save()
    assert editor.editing
    assert path.read_text(encoding="utf-8") == prior
    assert len(editor.zones) == 1


def test_bad_saved_data_starts_empty(tmp_path):
    path = tmp_path / "nicla_zones.json"
    path.write_text("{bad json", encoding="utf-8")
    assert load_zones(path) == []
    path.write_text(json.dumps({"version": 1, "points": []}), encoding="utf-8")
    assert load_zones(path) == []
    path.write_text(json.dumps({"version": 2, "zones": [[(0, 0), (0, 1), (1, 1)], "bad"]}),
                    encoding="utf-8")
    assert load_zones(path) == []


def test_max_zone_limit(tmp_path):
    path = tmp_path / "nicla_zones.json"
    editor = ZoneEditor(path)
    for _ in range(MAX_ZONES):
        draw(editor, [(20, 20), (100, 20), (100, 130), (20, 130)])
    assert len(editor.zones) == MAX_ZONES
    prior = path.read_text(encoding="utf-8")
    editor.begin()
    for x, y in [(20, 20), (100, 20), (100, 130), (20, 130)]:
        editor.add_corner(x, y, 320, 240)
    with pytest.raises(ValueError, match="Maximum"):
        editor.save()
    assert path.read_text(encoding="utf-8") == prior
