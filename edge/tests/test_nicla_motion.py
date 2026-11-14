"""Predictive motion tests use synthetic frames, no physical hazards."""
from edge.nicla_motion import PredictiveMotionMonitor


def box(cx, y, width=20):
    return (cx - width // 2, y - 60, cx + width // 2, y)


def test_car_approaching_standing_person_is_predicted():
    monitor = PredictiveMotionMonitor()
    events = []
    for i in range(5):
        # 320x240: car moves +35px/frame at 4 FPS; person stays still.
        events += monitor.update(
            [(10, 2, box(35 + i * 35, 180)), (20, 0, box(265, 180))],
            when=10 + i * 0.25, width=320, height=240)
    assert any(e.hazard_type == "vehicle_approaching_person" for e in events)
    assert monitor.active
    assert monitor.active[0].source_id == 10
    assert monitor.active[0].target_id == 20


def test_stationary_car_and_car_driving_away_never_alert():
    for positions in ([80, 80, 80, 80, 80], [170, 140, 110, 80, 50]):
        monitor = PredictiveMotionMonitor()
        warnings = []
        for i, x in enumerate(positions):
            warnings += monitor.update(
                [(1, 2, box(x, 180)), (2, 0, box(280, 180))],
                30 + i * 0.25, 320, 240)
        assert warnings == []


def test_person_approaching_sharp_zone_is_predicted():
    monitor = PredictiveMotionMonitor()
    # Marked prop is at x 220..280 in the image.
    region = [(220, 110), (280, 110), (280, 210), (220, 210)]
    events = []
    for i in range(5):
        events += monitor.update(
            [(5, 0, box(65 + i * 30, 180))],
            50 + i * 0.25, 320, 240, sharp_zones=[(1, region)])
    assert any(x.hazard_type == "person_approaching_marked_sharp_zone" for x in events)


def test_person_leaving_sharp_zone_no_alert():
    monitor = PredictiveMotionMonitor()
    region = [(220, 110), (280, 110), (280, 210), (220, 210)]
    all_events = []
    for i in range(5):
        all_events.extend(monitor.update(
            [(5, 0, box(185 - i * 25, 180))],
            60 + i * 0.25, 320, 240, sharp_zones=[(1, region)]))
    assert all_events == []


def test_no_tracks_no_prediction_and_reset():
    monitor = PredictiveMotionMonitor()
    assert monitor.update([(None, 0, box(200, 180)), (None, 2, box(100, 180))],
                          1, 320, 240) == []
    monitor.reset()
    assert not monitor.active
    assert not monitor.tracks


def test_two_frames_required_for_alert():
    monitor = PredictiveMotionMonitor(confirm_frames=3)
    person = (20, 0, box(260, 180))
    for i in range(2):
        assert monitor.update([(10, 2, box(60+i*20, 180)), person],
                              70+i*0.25, 320, 240) == []
