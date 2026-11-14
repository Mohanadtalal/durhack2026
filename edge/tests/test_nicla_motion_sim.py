"""Safe simulated positive and negative tests without YOLO, hardware or OpenCV."""
from edge.nicla_motion_sim import evaluate, samples, WIDTH, HEIGHT


def test_simulated_truck_approaches_worker_without_marking_zones():
    assert evaluate("approach", render=False) > 0


def test_simulated_truck_passes_worker_at_different_ground_position():
    assert evaluate("pass", render=False) == 0


def test_simulated_detection_stream_has_stable_ids_and_finite_boxes():
    frames = list(samples("approach"))
    assert len(frames) >= 20
    assert frames[0].vehicle_box[0] < frames[5].vehicle_box[0]
    assert frames[0].person_box == frames[-1].person_box
    for f in frames:
        for x1, y1, x2, y2 in (f.vehicle_box, f.person_box):
            assert 0 <= x1 < x2 < WIDTH
            assert 0 <= y1 < y2 < HEIGHT
