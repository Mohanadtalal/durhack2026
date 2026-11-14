"""Predictive motion tests use synthetic frames, no physical hazards."""
from edge.nicla_motion import PredictiveMotionMonitor

ROAD = [(10, 130), (310, 130), (310, 230), (10, 230)]

def lane():
    return [(1, ROAD)]


def box(cx, y, width=20):
    return (cx - width // 2, y - 60, cx + width // 2, y)


def test_car_approaching_standing_person_is_predicted():
    monitor = PredictiveMotionMonitor()
    events = []
    for i in range(5):
        # 320x240: car moves +35px/frame at 4 FPS; person stays still.
        events += monitor.update(
            [(10, 2, box(35 + i * 35, 180)), (20, 0, box(265, 180))],
            when=10 + i * 0.25, width=320, height=240, road_zones=lane())
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
                30 + i * 0.25, 320, 240, road_zones=lane())
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
                              70+i*0.25, 320, 240, road_zones=lane()) == []


def test_person_approaching_parked_car_is_not_vehicle_alert():
    # A moving person cannot make a stationary car appear to approach them.
    monitor = PredictiveMotionMonitor()
    events = []
    for i in range(5):
        events.extend(monitor.update(
            [(10, 2, box(210, 180)), (20, 0, box(30 + i * 35, 180))],
            80 + 0.25 * i, 320, 240, road_zones=lane()))
    assert not any(e.hazard_type == "vehicle_approaching_person" for e in events)


def test_unmarked_sharp_region_never_triggers():
    monitor = PredictiveMotionMonitor()
    events = []
    for i in range(5):
        events.extend(monitor.update(
            [(5, 0, box(65 + i * 30, 180))],
            95 + 0.25 * i, 320, 240))
    assert not events


def test_diagnostics_reveal_missing_car_or_person():
    monitor = PredictiveMotionMonitor()
    monitor.update([(1, 0, box(250, 180))], 1.0, 320, 240)
    assert "NO VEHICLE DETECTED/TRACKED" in monitor.debug_summary
    monitor.update([(2, 2, box(90, 180))], 1.25, 320, 240)
    assert "NO PERSON DETECTED/TRACKED" in monitor.debug_summary


def test_diagnostics_stationary_car_and_approach_candidate():
    monitor = PredictiveMotionMonitor()
    for i in range(4):
        monitor.update([(10, 2, box(70, 180)), (20, 0, box(270, 180))],
                       10 + i * .25, 320, 240, road_zones=lane())
    assert "CAR NOT MOVING TOWARD PERSON" in monitor.debug_summary

    monitor.reset()
    for i in range(5):
        monitor.update([(10, 2, box(35 + i * 35, 180)),
                        (20, 0, box(265, 180))],
                       20 + i * .25, 320, 240, road_zones=lane())
    assert "ROAD CONFLICT CANDIDATE" in monitor.debug_summary
    assert "VEHICLE WARNING ACTIVE" in monitor.debug_summary


def test_automatic_vehicle_prediction_needs_no_road_polygon():
    monitor = PredictiveMotionMonitor()
    events = []
    for i in range(6):
        events.extend(monitor.update(
            [(10, 2, box(35 + i * 35, 180)), (20, 0, box(265, 180))],
            100 + i * .25, 320, 240))
    assert any(e.hazard_type == "vehicle_approaching_person" for e in events)
    assert "AUTOMATIC PATH CONFLICT" in monitor.debug_summary


def test_pedestrian_waiting_on_pavement_not_collision_risk():
    monitor = PredictiveMotionMonitor()
    # Vehicle is in road (foot y=180); person is outside (foot y=150).
    road = [(10, 169), (310, 169), (310, 230), (10, 230)]
    events = []
    for i in range(6):
        events.extend(monitor.update(
            [(10, 2, box(35 + 30 * i, 180)),
             (20, 0, box(250, 150))],
            120 + i * .25, 320, 240, road_zones=[(1, road)]))
    assert not any(x.hazard_type == "vehicle_approaching_person" for x in events)


def test_car_outside_marked_road_cannot_trigger():
    monitor = PredictiveMotionMonitor()
    road = [(10, 201), (310, 201), (310, 230), (10, 230)]
    events = []
    for i in range(6):
        events.extend(monitor.update(
            [(10, 2, box(35 + 30 * i, 180)),
             (20, 0, box(250, 180))],
            130 + i * .25, 320, 240, road_zones=[(1, road)]))
    assert events == []


def test_small_pedestrian_box_jitter_does_not_create_road_entry():
    monitor = PredictiveMotionMonitor()
    # Person stays off marked road, even with +-2 pixel bbox movements.
    road = [(10, 165), (310, 165), (310, 230), (10, 230)]
    events = []
    for i in range(7):
        events.extend(monitor.update(
            [(10, 2, box(30 + i * 30, 180)),
             (20, 0, box(250, 160 + (i % 3 - 1) * 2))],
            140 + i * .25, 320, 240, road_zones=[(1, road)]))
    assert events == []


def test_unmarked_pavement_pass_by_suppressed_by_ground_contact():
    monitor = PredictiveMotionMonitor()
    warnings = []
    # Vehicle footpoint y=180; stationary worker feet y=155, on an
    # apparently different ground level/image row. NO manually drawn areas.
    for i in range(6):
        warnings.extend(monitor.update(
            [(30, 2, box(35 + i * 35, 180)), (40, 0, box(265, 155))],
            200 + i * .25, 320, 240))
    assert not any(w.hazard_type == "vehicle_approaching_person" for w in warnings)
    assert any(key in monitor.debug_summary for key in (
        "FOOTPOINT DEPTH MISMATCH", "PATHS NOT CLOSING",
        "PROJECTED PATHS TOO FAR APART", "OBJECTS TOO CLOSE/FAR IN FRAME"))


def test_truck_moving_toward_static_worker_is_detected_without_zones():
    monitor = PredictiveMotionMonitor()
    warnings = []
    for i in range(6):
        warnings.extend(monitor.update(
            [(30, 7, box(35 + i * 35, 180)), (40, 0, box(265, 180))],
            240 + i * .25, 320, 240))
    assert any(w.hazard_type == "vehicle_approaching_person" for w in warnings)


def test_existing_manual_road_area_is_optional_restriction():
    lane_far_away = [(10, 30), (310, 30), (310, 70), (10, 70)]
    monitor = PredictiveMotionMonitor()
    warnings = []
    for i in range(6):
        warnings.extend(monitor.update(
            [(30, 2, box(35 + i * 35, 180)), (40, 0, box(265, 180))],
            260 + i * .25, 320, 240, road_zones=[(1, lane_far_away)]))
    assert not warnings


def test_prediction_requires_consistent_direction_over_multiple_frames():
    monitor = PredictiveMotionMonitor()
    warnings = []
    for i, x in enumerate([35, 40, 35, 40, 35, 40]):
        warnings.extend(monitor.update(
            [(30, 2, box(x, 180)), (40, 0, box(265, 180))],
            290 + i * .25, 320, 240))
    assert not warnings
