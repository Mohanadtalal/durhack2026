"""Regression coverage for the manual T-key multi-object tracker.

Requires no camera, OpenCV, YOLO, backend, network or USB hardware.
"""
import ast
import inspect
import textwrap
from types import SimpleNamespace

import pytest

from edge.manual_tracking import create_manual_tracker, update_manual_trackers
from edge import nicla_detector


class FakeTracker:
    def __init__(self, box, succeeds=True):
        self.box = box
        self.succeeds = succeeds
        self.calls = 0

    def update(self, frame):
        self.calls += 1
        return self.succeeds, self.box


def test_multiple_objects_update_once_each_and_keep_positions():
    first = FakeTracker((10.8, 20, 30, 40))
    second = FakeTracker((75, 12, 25, 30))
    trackers = [first, second]
    same_list = trackers
    boxes, lost = update_manual_trackers(trackers, object())
    assert boxes == [(10, 20, 30, 40), (75, 12, 25, 30)]
    assert lost == 0
    assert first.calls == second.calls == 1
    assert trackers is same_list and trackers == [first, second]


def test_one_lost_tracker_does_not_stop_other_tracks():
    lost_one = FakeTracker((0, 0, 0, 0), succeeds=False)
    remaining = FakeTracker((25, 25, 10, 10))
    trackers = [lost_one, remaining]
    boxes, lost = update_manual_trackers(trackers, object())
    assert boxes == [(25, 25, 10, 10)]
    assert lost == 1
    assert trackers == [remaining]
    boxes, lost = update_manual_trackers(trackers, object())
    assert boxes == [(25, 25, 10, 10)] and lost == 0


def test_create_tracker_prefers_csrt_then_falls_back_to_mil():
    csrt = object()
    mil = object()
    direct = SimpleNamespace(
        TrackerCSRT_create=lambda: csrt, TrackerMIL_create=lambda: mil
    )
    assert create_manual_tracker(direct) is csrt
    legacy = SimpleNamespace(TrackerCSRT_create=lambda: csrt)
    assert create_manual_tracker(SimpleNamespace(legacy=legacy, TrackerMIL_create=lambda: mil)) is csrt
    assert create_manual_tracker(SimpleNamespace(TrackerMIL_create=lambda: mil)) is mil


def test_missing_tracker_has_actionable_error():
    with pytest.raises(RuntimeError, match="opencv-contrib-python"):
        create_manual_tracker(SimpleNamespace())


def test_camera_loop_processes_frames_even_with_zero_manual_trackers():
    """Regression: PR #16 accidentally dedented frame processing below while."""
    tree = ast.parse(textwrap.dedent(inspect.getsource(nicla_detector.run)))
    # The camera loop must contain snapshot_gray() and the manual update.
    loops = [node for node in ast.walk(tree) if isinstance(node, ast.While)]
    def includes_call(loop, method):
        return any(isinstance(n, ast.Call) and isinstance(n.func, ast.Attribute)
                   and n.func.attr == method for stmt in loop.body for n in ast.walk(stmt))
    frame_loops = [loop for loop in loops if includes_call(loop, "snapshot_gray")]
    assert frame_loops
    # The outer reconnect loop also contains nested calls; choose the
    # innermost frame-capture loop, where every frame must be processed.
    loop = min(frame_loops, key=lambda node: node.end_lineno - node.lineno)
    assert includes_call(loop, "update_manual_trackers")
    assert includes_call(loop, "imshow")
    assert includes_call(loop, "selectROI")
    assert includes_call(loop, "report")
