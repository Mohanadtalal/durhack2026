"""Clear all user-configured camera boxes without erasing incident history.

Operate on the camera owner thread only (never on the HTTP request thread).
The saved polygons are removed from disk; current detection still runs.
"""


def clear_saved_camera_boxes(editor, road_editor, occupancies, monitors, preview=None):
    """Clear fixed danger/road areas and their detector states."""
    editor.reset()
    road_editor.reset()
    occupancies.clear()
    monitors.clear()
    if preview is not None:
        preview.update_zones([])
