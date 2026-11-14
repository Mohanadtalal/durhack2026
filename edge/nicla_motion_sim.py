"""Safe, deterministic SiteGuardian motion predictor demo.

This exercises the REAL PredictiveMotionMonitor with synthetic tracked boxes.
It does NOT run YOLO, ByteTrack, Nicla, backend events or hardware LEDs.

    python -m edge.nicla_motion_sim
    python -m edge.nicla_motion_sim --scenario approach
    python -m edge.nicla_motion_sim --no-video

Two scenarios: a truck closing toward a worker's projected ground position,
and a truck passing in a visually different ground row. No zones are marked.
"""
import argparse
from dataclasses import dataclass
from pathlib import Path

from .nicla_motion import PredictiveMotionMonitor

WIDTH, HEIGHT, FPS, COUNT = 640, 360, 8, 34
VEHICLE_ID = 100
WORKER_ID = 200
VEHICLE_LABEL = "TRUCK #100 (synthetic detection)"
PERSON_LABEL = "WORKER #200 (synthetic detection)"


@dataclass(frozen=True)
class Sample:
    time: float
    vehicle_box: tuple
    person_box: tuple


def _box(cx, foot_y, width, height):
    return (int(cx - width / 2), int(foot_y - height),
            int(cx + width / 2), int(foot_y))


def samples(scenario, count=COUNT):
    """Create stable IDs with motion/box sizes consistent with video frames."""
    if scenario not in ("approach", "pass"):
        raise ValueError("Choose 'approach' or 'pass'")
    if count < 1:
        raise ValueError("Frame count must be positive")

    # Same ground row => projected vehicle/person contact point can converge.
    # Different ground rows => image tracks may overlap but no contact warning.
    worker_foot = 270 if scenario == "approach" else 155
    for index in range(count):
        # A truck moves toward x=520 before braking to a stop. No real hazard.
        truck_cx = min(100 + index * 15, 445)
        yield Sample(
            time=index / FPS,
            vehicle_box=_box(truck_cx, 270, 106, 68),
            person_box=_box(520, worker_foot, 36, 105),
        )


def evaluate(scenario, render=False, destination=None):
    """Return number of NEW confirmed predictions from real motion monitor.

    Render only affects creating MP4; it never influences prediction results.
    """
    monitor = PredictiveMotionMonitor()
    cv2 = None
    writer = None
    if render:
        import cv2
        if destination is None:
            raise ValueError("MP4 destination required when rendering")
        path = Path(destination)
        path.parent.mkdir(parents=True, exist_ok=True)
        writer = cv2.VideoWriter(str(path), cv2.VideoWriter_fourcc(*"mp4v"),
                                 float(FPS), (WIDTH, HEIGHT))
        if not writer.isOpened():
            raise RuntimeError(f"Could not open output MP4: {path}")
    found = []
    first_alert_at = None
    try:
        for sample in samples(scenario):
            detections = [
                (VEHICLE_ID, 7, sample.vehicle_box),  # COCO truck
                (WORKER_ID, 0, sample.person_box),    # COCO person
            ]
            events = monitor.update(detections, sample.time, WIDTH, HEIGHT)
            warnings = [e for e in events
                        if e.hazard_type == "vehicle_approaching_person"]
            if warnings:
                found.extend(warnings)
                if first_alert_at is None:
                    first_alert_at = sample.time
                    for warning in warnings:
                        print(f"[SIM HAZARD] {scenario} at {sample.time:.2f}s: "
                              f"VEHICLE {warning.source_id} -> WORKER {warning.target_id} "
                              f"| projected image encounter {warning.seconds_ahead:.2f}s")
            if writer is not None:
                frame = draw_scene(cv2, scenario, sample, monitor)
                writer.write(frame)
    finally:
        if writer is not None:
            writer.release()
    if destination and render:
        print(f"[SIM] Saved {destination}")
    print(f"[SIM RESULT] {scenario}: confirmed_warnings={len(found)} "
          f"| first_alert={first_alert_at if first_alert_at is not None else 'none'}")
    return len(found)


def draw_scene(cv2, scenario, sample, monitor):
    """Stylised visualization only; model receives synthetic boxes, not pixels."""
    import numpy as np

    frame = np.full((HEIGHT, WIDTH, 3), (53, 65, 77), dtype=np.uint8)
    # Non-interactive virtual background, no manually drawn polygon.
    cv2.rectangle(frame, (0, 280), (WIDTH, HEIGHT), (94, 99, 104), -1)
    cv2.line(frame, (0, 280), (WIDTH, 280), (170, 184, 192), 2)
    cv2.putText(frame, "SIMULATION | TRACKED BOXES PROVIDED DIRECTLY",
                (14, 30), cv2.FONT_HERSHEY_SIMPLEX, .66, (255, 255, 255), 2)
    cv2.putText(frame, f"SCENARIO: {scenario.upper()} | t={sample.time:.2f}s",
                (14, 58), cv2.FONT_HERSHEY_SIMPLEX, .58, (255, 255, 255), 2)

    vx1, vy1, vx2, vy2 = sample.vehicle_box
    px1, py1, px2, py2 = sample.person_box

    # A labelled toy truck illustration. Its detection box is predetermined.
    cv2.rectangle(frame, (vx1 + 5, vy1 + 16), (vx2 - 5, vy2 - 10), (185, 145, 57), -1)
    cv2.rectangle(frame, (vx1 + 58, vy1 + 5), (vx2 - 7, vy2 - 10), (210, 175, 90), -1)
    cv2.circle(frame, (vx1 + 20, vy2 - 6), 9, (32, 34, 37), -1)
    cv2.circle(frame, (vx2 - 21, vy2 - 6), 9, (32, 34, 37), -1)
    cv2.rectangle(frame, (vx1, vy1), (vx2, vy2), (0, 205, 255), 2)

    # Labelled virtual worker with high-vis vest and hard hat.
    center = (px1 + px2) // 2
    cv2.circle(frame, (center, py1 + 19), 11, (181, 201, 218), -1)
    cv2.ellipse(frame, (center, py1 + 12), (15, 7), 0, 180, 360, (45, 219, 241), -1)
    cv2.line(frame, (center, py1 + 31), (center, py1 + 72), (55, 209, 240), 11)
    cv2.line(frame, (center, py1 + 72), (center - 11, py2 - 3), (210, 219, 225), 5)
    cv2.line(frame, (center, py1 + 72), (center + 11, py2 - 3), (210, 219, 225), 5)
    cv2.rectangle(frame, (px1, py1), (px2, py2), (69, 213, 94), 2)

    cv2.circle(frame, ((vx1 + vx2) // 2, vy2), 4, (0, 205, 255), -1)
    cv2.circle(frame, ((px1 + px2) // 2, py2), 4, (69, 213, 94), -1)
    cv2.putText(frame, "TRUCK #100", (max(5, vx1), max(80, vy1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX, .43, (0, 205, 255), 1)
    cv2.putText(frame, "WORKER #200", (max(5, px1 - 15), max(82, py1 - 8)),
                cv2.FONT_HERSHEY_SIMPLEX, .43, (69, 213, 94), 1)

    if monitor.active:
        cv2.rectangle(frame, (0, HEIGHT - 47), (WIDTH, HEIGHT), (0, 0, 180), -1)
        cv2.putText(frame, "POTENTIAL VEHICLE-WORKER APPROACH",
                    (12, HEIGHT - 16), cv2.FONT_HERSHEY_SIMPLEX,
                    .64, (255, 255, 255), 2)
    else:
        cv2.rectangle(frame, (0, HEIGHT - 47), (WIDTH, HEIGHT), (45, 55, 59), -1)
        cv2.putText(frame, monitor.debug_summary[:90],
                    (12, HEIGHT - 17), cv2.FONT_HERSHEY_SIMPLEX,
                    .37, (200, 236, 249), 1)
    cv2.putText(frame, "Simulated detections: YOLO / tracking NOT tested",
                (12, 81), cv2.FONT_HERSHEY_SIMPLEX, .42, (220, 220, 220), 1)
    return frame


def main():
    parser = argparse.ArgumentParser(description=(
        "Run deterministic positive/negative tests of SiteGuardian motion prediction "
        "using artificial tracked boxes; not a physical safety test"))
    parser.add_argument("--scenario", choices=("approach", "pass", "both"),
                        default="both")
    parser.add_argument("--output-dir", default="data/simulations",
                        help="Directory for rendered simulation videos")
    parser.add_argument("--no-video", action="store_true",
                        help="Test predictor without OpenCV or generating MP4")
    args = parser.parse_args()
    choices = ("approach", "pass") if args.scenario == "both" else (args.scenario,)
    good = True
    for name in choices:
        count = evaluate(name, render=not args.no_video,
                         destination=str(Path(args.output_dir) / (name + ".mp4")))
        expected_positive = name == "approach"
        passed = (count > 0) if expected_positive else (count == 0)
        print(f"[SIM CHECK] {name.upper()}: {'PASS' if passed else 'FAIL'} "
              f"({'warning expected' if expected_positive else 'no warning expected'})")
        good = good and passed
    if not good:
        raise SystemExit("[SIM CHECK] FAIL: prediction did not match expectation")
    print("[SIM CHECK] PASS: all selected scenario expectations matched.")
    print("[SIM] This verifies prediction logic ONLY, not YOLO, ByteTrack, USB, "
          "distance measurement or real-world safety.")


if __name__ == "__main__":
    main()
