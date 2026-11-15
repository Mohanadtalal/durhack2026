"""Camera box reset deletes only camera regions, not alert evidence."""
from edge.camera_controls import clear_saved_camera_boxes
from edge.zone_editor import ZoneEditor


def _save_triangle(editor):
    editor.begin()
    for x, y in [(20, 20), (150, 20), (80, 160)]:
        editor.add_corner(x, y, 320, 240)
    editor.save()


def test_reset_removes_both_persisted_zone_types_and_live_states(tmp_path):
    danger = ZoneEditor(tmp_path / "nicla_zones.json")
    road = ZoneEditor(tmp_path / "road_zones.json")
    _save_triangle(danger)
    _save_triangle(road)
    danger.begin()
    danger.add_corner(10, 10, 320, 240)
    occupancy = [object()]
    monitors = [object()]

    class FakePreview:
        def __init__(self):
            self.zones = ["old"]
        def update_zones(self, zones):
            self.zones = zones

    preview = FakePreview()
    clear_saved_camera_boxes(danger, road, occupancy, monitors, preview)
    assert danger.zones == []
    assert road.zones == []
    assert not danger.editing and not road.editing
    assert not danger.path.exists() and not road.path.exists()
    assert not occupancy and not monitors
    assert preview.zones == []
