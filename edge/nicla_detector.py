"""SiteGuardian Nicla Vision: live zones, optional PPE, ToF, USB recovery, recording.

Default command preserves the previously tested person/zone/LED pipeline:
    python -m edge.nicla_detector --port COM9 --no-api --dwell 5
Extra features (independently opt in):
    python -m edge.nicla_detector --port COM9 --no-api --proximity-mm 800
    python -m edge.nicla_detector --port COM9 --no-api --record data/demo.mp4
    python -m edge.nicla_detector --port COM9 --no-api --ppe-weights models/ppe.pt

All warnings are prototype demonstrations, not certified construction alarms.
"""
import argparse
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .nicla_extra_rules import (
    PPE_HAZARDS, ProximityAlert, extract_ppe_hazards, supported_ppe_classes,
)
from .nicla_geometry import DebouncedOccupancy
from .nicla_recording import TimedFrameRecorder
from .nicla_motion import PredictiveMotionMonitor
from .nicla_usb import NiclaProtocolError, NiclaUSB
from .preview_server import PreviewServer, zones_for_editor
from .zone_editor import DEFAULT_ZONE_FILE, ZoneEditor, person_in_polygon
from .zone_rules import ZoneMonitor


def run(port, preview_only=False, no_api=False, dwell=8.0, weights="yolov8n.pt",
        zone_file=DEFAULT_ZONE_FILE, ppe_weights=None, proximity_mm=None,
        record_path=None, retry_seconds=2.0, predictive=False, sharp_zone_ids=(),
        motion_debug=False, road_file="data/nicla_road_conflicts.json",
        road_filter=False, stream_port=None, stream_host="127.0.0.1"):
    import cv2
    import numpy as np
    from .client import send_event, flush_pending

    if retry_seconds < 0.5:
        raise ValueError("retry_seconds must be at least 0.5")
    if preview_only and ppe_weights:
        raise ValueError("Remove --preview-only when using a PPE model.")
    if preview_only and predictive:
        raise ValueError("Predictive motion analysis requires YOLO; remove --preview-only.")
    if any(index < 1 for index in sharp_zone_ids):
        raise ValueError("Sharp zone indices start at 1.")
    if sharp_zone_ids and not predictive:
        raise ValueError("Marking a sharp zone requires --predictive.")
    if motion_debug and not predictive:
        raise ValueError("Motion diagnostics require --predictive.")

    person_model = None
    ppe_model = None
    if not preview_only:
        from ultralytics import YOLO
        print("[MODEL] Loading person detector:", weights)
        person_model = YOLO(weights)
    if ppe_weights:
        from ultralytics import YOLO
        print("[PPE] Loading separately trained PPE weights:", ppe_weights)
        ppe_model = YOLO(ppe_weights)
        classes = supported_ppe_classes(ppe_model.names)
        if not classes:
            raise ValueError("PPE model has no explicit no_helmet/no_vest classes. "
                             "Generic COCO person weights cannot detect missing PPE.")
        print("[PPE] Supported missing-equipment classes:", sorted(classes))

    editor = ZoneEditor(zone_file)
    road_editor = ZoneEditor(road_file)
    if road_filter and not road_editor.zones:
        raise ValueError("--road-filter needs a saved road area. First draw one "
                         "with L, clicks and S in normal --predictive mode.")
    active_editor = editor
    predictor = PredictiveMotionMonitor() if predictive else None
    sharp_zone_ids = set(sharp_zone_ids)
    occupancies = [DebouncedOccupancy(2) for _ in editor.zones]
    monitors = [ZoneMonitor(dwell_seconds=dwell) for _ in editor.zones]
    ppe_states = {kind: DebouncedOccupancy(2) for kind in PPE_HAZARDS}
    proximity = ProximityAlert(proximity_mm) if proximity_mm is not None else None
    distance_mm = None
    distance_unavailable_logged = False
    warning_active = False
    recording = None
    nframes = 0
    t0 = time.monotonic()
    last_motion_debug_log = 0.0
    window = "SiteGuardian: Nicla Vision"
    frame_size = [320, 240]
    running = True
    preview = None

    def on_mouse(event, x, y, flags, userdata):
        if event == cv2.EVENT_LBUTTONDOWN:
            active_editor.add_corner(x, y, frame_size[0], frame_size[1])

    def report(hazard_type, zone_id, severity="warning", metadata=None):
        print("[HAZARD]", hazard_type, "|", zone_id)
        if no_api:
            return
        send_event({
            "event_id": str(uuid4()),
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "source_id": "nicla-vision-01",
            "zone_id": zone_id,
            "hazard_type": hazard_type,
            "severity": severity,
            "description": "Nicla demo detection: " + hazard_type.replace("_", " "),
            "metadata": {
                "camera": "nicla_vision",
                "simulated": False,
                "safety_certified": False,
                **(metadata or {}),
            },
        })

    print("Opening Nicla Vision:", port, "| close OpenMV IDE first")
    print("Keys: E danger zone, L road zone, left-click corners, S save, U undo, C cancel,")
    print("R clear danger zones, K clear road zones, Q quit.")
    print("Loaded", len(editor.zones), "danger zones from", editor.path)
    print("[ROAD] Loaded", len(road_editor.zones), "vehicle conflict areas from",
          road_editor.path)
    if predictor:
        print("[PREDICT] Tracking persons and cars, warning on converging image paths.")
        if sharp_zone_ids:
            print("[PREDICT] Manually marked sharp-prop zones:", sorted(sharp_zone_ids))
            print("[PREDICT] This does NOT detect sharp objects or verify walking backward.")
        print("[PREDICT] Use a fixed Nicla camera. Predictions are not physical collision distances.")
        if road_filter:
            print("[PREDICT] Optional road-region filtering ENABLED")
        else:
            print("[PREDICT] AUTOMATIC vehicle/worker assessment enabled - no zones required.")
    if proximity is not None:
        print("[ToF] Forward object alert threshold:", proximity.threshold_mm, "mm")
        print("[ToF] Requires updated main.py on Nicla. Does not measure person distance.")
    if record_path:
        print("[RECORD] Saving annotated demo to", record_path)

    try:
        if stream_port is not None:
            preview = PreviewServer(stream_host, stream_port)
            preview.update_zones(zones_for_editor(editor, sharp_zone_ids))
            host, port_number = preview.address
            print(f"[STREAM] Local annotated MJPEG http://{host}:{port_number}/stream.mjpg")
            print(f"[STREAM] Camera and zone status http://{host}:{port_number}/status.json")
            if stream_host not in ("127.0.0.1", "localhost", "::1"):
                print("[STREAM WARNING] Non-loopback host: this prototype endpoint has "
                      "NO authentication; use only on a trusted isolated network.")
        cv2.namedWindow(window, cv2.WINDOW_AUTOSIZE)
        cv2.setMouseCallback(window, on_mouse)
        while running:
            try:
                with NiclaUSB.connect(port, timeout=5.0) as nicla:
                    if not nicla.ping():
                        raise NiclaProtocolError("Nicla did not reply PONG")
                    nicla.set_warning(False, force=True)
                    print("[USB] Connected and responding on", port)
                    warning_active = False
                    last_distance_poll = 0.0

                    while running:
                        raw = nicla.snapshot_gray()
                        gray = np.frombuffer(raw, dtype=np.uint8).reshape((240, 320))
                        frame = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
                        height, width = frame.shape[:2]
                        frame_size[:] = [width, height]
                        regions = editor.pixels(width, height)
                        road_regions = road_editor.pixels(width, height)
                        inference_frame = frame.copy()
                        now = time.monotonic()
                        events = []

                        # Track people and cars only when predictive mode is enabled.
                        # Standard person-only detection is unchanged by default.
                        person_boxes = []
                        tracked = []
                        if person_model is not None:
                            if predictor is not None:
                                people_result = person_model.track(
                                    inference_frame, persist=True, tracker="bytetrack.yaml",
                                    conf=0.35, classes=[0, 2, 5, 7], verbose=False
                                )[0]
                                boxes = people_result.boxes
                                xyxy = boxes.xyxy.cpu().numpy()
                                class_ids = boxes.cls.cpu().numpy()
                                ids = (boxes.id.cpu().numpy() if boxes.id is not None
                                       else [None] * len(xyxy))
                                for box, class_id, track_id in zip(xyxy, class_ids, ids):
                                    coords = tuple(int(v) for v in box)
                                    kind = int(class_id)
                                    ident = int(track_id) if track_id is not None else None
                                    if ident is not None:
                                        tracked.append((ident, kind, coords))
                                    if kind == 0:
                                        person_boxes.append(coords)
                                    x1, y1, x2, y2 = coords
                                    color = (50, 220, 120) if kind == 0 else (0, 165, 255)
                                    cv2.rectangle(frame, (x1, y1), (x2, y2), color, 2)
                                    kind_name = {0: "PERSON", 2: "CAR",
                                                 5: "BUS", 7: "TRUCK"}.get(kind, "VEHICLE")
                                    cv2.putText(
                                        frame, f"{kind_name} #{ident if ident is not None else '?'}",
                                        (x1, max(20, y1 - 4)), cv2.FONT_HERSHEY_SIMPLEX,
                                        .35, color, 1,
                                    )
                            else:
                                people_result = person_model.predict(
                                    inference_frame, conf=0.45, classes=[0], verbose=False
                                )[0]
                                person_boxes = [
                                    tuple(int(v) for v in box)
                                    for box in people_result.boxes.xyxy.cpu().numpy()
                                ]
                                for x1, y1, x2, y2 in person_boxes:
                                    cv2.rectangle(frame, (x1, y1), (x2, y2),
                                                  (50, 220, 120), 2)

                        if len(regions) != len(occupancies):
                            raise RuntimeError("Zone tracker and saved zones differ.")
                        for i, region in enumerate(regions):
                            observed = person_in_polygon(person_boxes, region)
                            occupancies[i].update(observed)
                            for event_type in monitors[i].update(occupancies[i].inside, now):
                                events.append((
                                    event_type, f"nicla-zone-{i + 1}",
                                    "high" if event_type == "prolonged_exposure" else "warning",
                                    {"virtual_zone": True, "zone_index": i + 1,
                                     "distance_calibrated": False},
                                ))

                        # PPE: requires separate weights trained with explicit missing labels.
                        ppe_findings = []
                        if ppe_model is not None:
                            result = ppe_model.predict(inference_frame, conf=0.45, verbose=False)[0]
                            detections = zip(
                                result.boxes.cls.cpu().numpy(),
                                result.boxes.conf.cpu().numpy(),
                                result.boxes.xyxy.cpu().numpy(),
                            )
                            ppe_findings = extract_ppe_hazards(ppe_model.names, detections)
                            for kind, (x1, y1, x2, y2), confidence in ppe_findings:
                                cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                                cv2.putText(frame, f"{kind} {confidence:.2f}", (x1, max(18, y1 - 4)),
                                            cv2.FONT_HERSHEY_SIMPLEX, .37, (0, 0, 255), 1)
                            for kind in PPE_HAZARDS:
                                previous = ppe_states[kind].inside
                                active = any(found == kind for found, _, _ in ppe_findings)
                                current = ppe_states[kind].update(active)
                                if current and not previous:
                                    events.append((
                                        kind, "nicla-camera-view", "warning",
                                        {"detection_mode": "explicit_missing_ppe_label",
                                         "model_file": Path(ppe_weights).name},
                                    ))

                        # ToF sensor is OPTIONAL and forward-facing, not per-person.
                        if proximity is not None and now - last_distance_poll >= 0.5:
                            last_distance_poll = now
                            distance_mm = nicla.distance_mm()
                            if distance_mm is None and not distance_unavailable_logged:
                                print("[ToF] No valid reading (sensor absent/not ready).")
                                distance_unavailable_logged = True
                            if distance_mm is not None:
                                distance_unavailable_logged = False
                            entered, cleared = proximity.update(distance_mm)
                            if entered:
                                events.append((
                                    "proximity_warning", "nicla-forward-tof", "warning",
                                    {"distance_mm": distance_mm, "threshold_mm": proximity_mm,
                                     "measurement": "forward_object_range"},
                                ))
                            if cleared:
                                print("[ToF] Forward proximity cleared")

                        # Predictive hazards are optional. Sharp prop locations
                        # are operator-marked existing zones, NOT AI-recognised tools.
                        if predictor is not None:
                            marked = [(i + 1, polygon) for i, polygon in enumerate(regions)
                                      if i + 1 in sharp_zone_ids]
                            for prediction in predictor.update(
                                    tracked, now, width, height, sharp_zones=marked,
                                    road_zones=([(i + 1, poly)
                                                 for i, poly in enumerate(road_regions)]
                                                if road_filter else ())):
                                if prediction.hazard_type == "vehicle_approaching_person":
                                    zone_id = f"nicla-car-{prediction.source_id}"
                                    extra = {"vehicle_track_id": prediction.source_id,
                                             "person_track_id": prediction.target_id}
                                else:
                                    zone_id = f"nicla-zone-{prediction.target_id}"
                                    extra = {"person_track_id": prediction.source_id,
                                             "manually_marked_sharp_zone": prediction.target_id}
                                events.append((
                                    prediction.hazard_type, zone_id, "warning",
                                    {**extra, "screen_plane_prediction": True,
                                     "not_calibrated": True,
                                     "horizon_seconds": round(prediction.seconds_ahead, 2)},
                                ))

                        # Red LED is driven by ANY configured hazard source.
                        in_zone = any(state.inside for state in occupancies)
                        ppe_alert = any(state.inside for state in ppe_states.values())
                        tof_alert = proximity.near if proximity is not None else False
                        predicted_alert = bool(predictor.active) if predictor else False
                        should_warn = in_zone or ppe_alert or tof_alert or predicted_alert
                        if should_warn != warning_active:
                            nicla.set_warning(should_warn)
                            warning_active = should_warn
                            print("[LOCAL LED]", "RED - hazard present" if should_warn else "OFF - clear")

                        for event_type, zone_id, severity, metadata in events:
                            report(event_type, zone_id, severity, metadata)

                        # Magenta road/crossing regions are separate from
                        # danger zones; they don't trigger ordinary zone alerts.
                        for i, region in enumerate(road_regions if road_filter else []):
                            cv2.polylines(frame, [np.array(region, dtype=np.int32)],
                                          True, (255, 80, 190), 2)
                            rx = min(x for x, y in region)
                            ry = min(y for x, y in region)
                            cv2.putText(frame, f"ROAD CONFLICT {i + 1}",
                                        (max(4, rx), max(25, ry - 5)),
                                        cv2.FONT_HERSHEY_SIMPLEX, .34, (255, 80, 190), 1)

                        # Draw each saved danger-zone polygon independently.
                        for i, region in enumerate(regions):
                            color = (0, 0, 255) if occupancies[i].inside else (0, 190, 70)
                            cv2.polylines(frame, [np.array(region, dtype=np.int32)], True, color, 2)
                            label_x = min(x for x, y in region)
                            label_y = min(y for x, y in region)
                            title = (f"MARKED SHARP ZONE {i + 1}"
                                     if i + 1 in sharp_zone_ids else f"ZONE {i + 1}")
                            cv2.putText(frame, title,
                                        (max(4, label_x), max(46, label_y - 7)),
                                        cv2.FONT_HERSHEY_SIMPLEX, .40, color, 2)
                        if not regions:
                            cv2.putText(frame, "NO ZONES - press E to add", (5, 40),
                                        cv2.FONT_HERSHEY_SIMPLEX, .40, (0, 255, 255), 1)
                        if predictor is not None:
                            # Draw one-second, image-plane motion arrows.
                            # They represent optical motion, not physical metres.
                            for track in predictor.tracks.values():
                                if track.samples < 2 or now - track.timestamp > 0.3:
                                    continue
                                if abs(track.vx) + abs(track.vy) < 0.025:
                                    continue
                                start = (
                                    max(0, min(width - 1, int(track.xy[0] * width))),
                                    max(0, min(height - 1, int(track.xy[1] * height))),
                                )
                                end = (
                                    max(0, min(width - 1, int((track.xy[0] + track.vx) * width))),
                                    max(0, min(height - 1, int((track.xy[1] + track.vy) * height))),
                                )
                                tint = (0, 170, 255) if track.class_id == 2 else (255, 220, 0)
                                cv2.arrowedLine(frame, start, end, tint, 2, tipLength=0.25)
                            if motion_debug:
                                diagnostic = predictor.debug_summary
                                cv2.putText(
                                    frame, diagnostic[:65], (4, height - 63),
                                    cv2.FONT_HERSHEY_SIMPLEX, .28, (0, 255, 255), 1
                                )
                                if now - last_motion_debug_log >= 1.5:
                                    print("[MOTION DEBUG]", diagnostic)
                                    last_motion_debug_log = now
                            for n, threat in enumerate(predictor.active[:2]):
                                if threat.hazard_type == "vehicle_approaching_person":
                                    label = f"APPROACH: VEHICLE {threat.source_id} -> PERSON {threat.target_id}"
                                    car = predictor.tracks.get(threat.source_id)
                                    person = predictor.tracks.get(threat.target_id)
                                    if car is not None and person is not None:
                                        a = (int(car.xy[0] * width), int(car.xy[1] * height))
                                        b = (int(person.xy[0] * width), int(person.xy[1] * height))
                                        cv2.line(frame, a, b, (0, 0, 255), 1)
                                else:
                                    label = f"APPROACH: PERSON {threat.source_id} -> SHARP {threat.target_id}"
                                cv2.putText(
                                    frame, label, (4, height - 34 - 15 * n),
                                    cv2.FONT_HERSHEY_SIMPLEX, .35, (0, 0, 255), 2
                                )
                        if active_editor.editing:
                            draft = active_editor.draft_pixels(width, height)
                            if len(draft) >= 2:
                                cv2.polylines(frame, [np.array(draft, dtype=np.int32)],
                                              False, (0, 255, 255), 2)
                            for i, (x, y) in enumerate(draft):
                                cv2.circle(frame, (x, y), 4, (0, 255, 255), -1)
                                cv2.putText(frame, str(i + 1), (x + 4, y - 4),
                                            cv2.FONT_HERSHEY_SIMPLEX, .34, (0, 255, 255), 1)
                            item = "ROAD" if active_editor is road_editor else "HAZARD"
                            cv2.putText(frame, f"DRAW {item} {len(draft)} points | S save U undo C cancel",
                                        (4, 28), cv2.FONT_HERSHEY_SIMPLEX,
                                        .33, (0, 255, 255), 1)

                        cv2.putText(frame,
                                    f"{len(regions)} hazard {len(road_regions)} road | E zone L road S save R/K clear Q quit",
                                    (4, 13), cv2.FONT_HERSHEY_SIMPLEX, .26,
                                    (255, 255, 255), 1)
                        if proximity is not None:
                            display = "--" if distance_mm is None else str(distance_mm)
                            cv2.putText(frame, f"ToF {display} mm | limit {proximity_mm}",
                                        (4, 58), cv2.FONT_HERSHEY_SIMPLEX, .37,
                                        (0, 0, 255) if proximity.near else (255, 255, 255), 1)
                        if ppe_model is not None:
                            cv2.putText(frame, "PPE model enabled", (4, 72),
                                        cv2.FONT_HERSHEY_SIMPLEX, .37, (255, 255, 255), 1)
                        nframes += 1
                        fps = nframes / max(0.001, time.monotonic() - t0)
                        cv2.putText(frame, f"Nicla USB | {fps:.1f} fps",
                                    (5, height - 8), cv2.FONT_HERSHEY_SIMPLEX,
                                    .45, (255, 255, 255), 1)

                        if record_path:
                            if recording is None:
                                target = Path(record_path)
                                target.parent.mkdir(parents=True, exist_ok=True)
                                writer = cv2.VideoWriter(
                                    str(target), cv2.VideoWriter_fourcc(*"mp4v"),
                                    10.0, (width, height)
                                )
                                if not writer.isOpened():
                                    writer.release()
                                    raise RuntimeError("Could not open MP4 output: " + str(target))
                                recording = TimedFrameRecorder(writer, fps=10.0)
                            recording.write(frame, at=time.monotonic())

                        if preview is not None:
                            preview.publish_frame(frame)
                        cv2.imshow(window, frame)
                        key = cv2.waitKey(1) & 0xFF
                        if key in (ord("q"), ord("Q")):
                            running = False
                            break
                        if key in (ord("e"), ord("E")):
                            road_editor.cancel()
                            active_editor = editor
                            editor.begin()
                            print("[ZONE] Drawing danger zone", len(editor.zones) + 1)
                        elif key in (ord("l"), ord("L")):
                            editor.cancel()
                            active_editor = road_editor
                            road_editor.begin()
                            print("[ROAD] Drawing vehicle conflict area",
                                  len(road_editor.zones) + 1)
                        elif key in (ord("u"), ord("U")):
                            active_editor.undo()
                        elif key in (ord("c"), ord("C")):
                            active_editor.cancel()
                            print("[ZONE] Cancelled unsaved polygon")
                        elif key in (ord("s"), ord("S")) and active_editor.editing:
                            try:
                                if active_editor.save():
                                    if active_editor is editor:
                                        occupancies.append(DebouncedOccupancy(2))
                                        monitors.append(ZoneMonitor(dwell_seconds=dwell))
                                        print("[ZONE] Saved danger zone", len(editor.zones))
                                        if preview is not None:
                                            preview.update_zones(
                                                zones_for_editor(editor, sharp_zone_ids))
                                    else:
                                        print("[ROAD] Saved road conflict area",
                                              len(road_editor.zones))
                            except (OSError, ValueError) as exc:
                                print("[ZONE] Save failed:", exc)
                        elif key in (ord("r"), ord("R")):
                            try:
                                editor.reset()
                                occupancies.clear()
                                monitors.clear()
                                print("[ZONE] Cleared danger zones")
                                if preview is not None:
                                    preview.update_zones([])
                            except OSError as exc:
                                print("[ZONE] Clear failed:", exc)
                        elif key in (ord("k"), ord("K")):
                            try:
                                road_editor.reset()
                                print("[ROAD] Cleared all road conflict areas")
                            except OSError as exc:
                                print("[ROAD] Clear failed:", exc)
            except (NiclaProtocolError, OSError) as exc:
                if not running:
                    break
                if recording is not None:
                    recording.pause(time.monotonic())
                print("[USB] Connection lost:", exc, "- retrying every", retry_seconds, "seconds")
                # State is unknown after a broken link. Re-arm detection on reconnect.
                warning_active = False
                occupancies = [DebouncedOccupancy(2) for _ in editor.zones]
                monitors = [ZoneMonitor(dwell_seconds=dwell) for _ in editor.zones]
                ppe_states = {kind: DebouncedOccupancy(2) for kind in PPE_HAZARDS}
                if predictor is not None:
                    predictor.reset()
                    # Tracker IDs must not persist across separate USB sessions.
                    if person_model is not None and getattr(person_model, "predictor", None):
                        for tracker in getattr(person_model.predictor, "trackers", []):
                            tracker.reset()
                proximity = ProximityAlert(proximity_mm) if proximity_mm is not None else None
                distance_mm = None
                deadline = time.monotonic() + retry_seconds
                while time.monotonic() < deadline:
                    if cv2.waitKey(100) & 0xFF in (ord("q"), ord("Q")):
                        running = False
                        break
    finally:
        if preview is not None:
            preview.close()
        if recording is not None:
            recording.release()
            print(f"[RECORD] Saved {recording.duration_seconds:.1f}s of video "
                  f"({recording.frames_written} frames) to {record_path}")
        cv2.destroyAllWindows()
        if not no_api:
            try:
                flush_pending()
            except Exception as exc:
                print("[QUEUE] Pending events remain unsent:", exc)


def main():
    parser = argparse.ArgumentParser(description="Nicla Vision hazard demo")
    parser.add_argument("--port", required=True, help="Windows COM port, e.g. COM9")
    parser.add_argument("--preview-only", action="store_true", help="Camera preview without YOLO")
    parser.add_argument("--no-api", action="store_true", help="Do not send incidents to backend")
    parser.add_argument("--dwell", type=float, default=8.0, help="Seconds for prolonged exposure")
    parser.add_argument("--weights", default="yolov8n.pt", help="YOLO model for person detection")
    parser.add_argument("--zone-file", default=str(DEFAULT_ZONE_FILE), help="Saved multi-zone JSON")
    parser.add_argument("--ppe-weights", help="Custom YOLO weights trained on explicit no_helmet/no_vest")
    parser.add_argument("--proximity-mm", type=int, help="Optional forward ToF alert threshold, 50-4000 mm")
    parser.add_argument("--record", help="Record annotated video to an MP4 path, e.g. data/demo.mp4")
    parser.add_argument("--retry-seconds", type=float, default=2.0, help="Retry USB after disconnect")
    parser.add_argument("--predictive", action="store_true",
                        help="Track cars and people to warn on converging image-plane paths")
    parser.add_argument("--sharp-zone", type=int, action="append", default=[],
                        help="Saved zone index containing a manually marked sharp prop; repeatable")
    parser.add_argument("--motion-debug", action="store_true",
                        help="Show why an approaching-car warning is not firing; requires --predictive")
    parser.add_argument("--road-file", default="data/nicla_road_conflicts.json",
                        help="Separate, optional vehicle/pedestrian conflict area polygons")
    parser.add_argument("--road-filter", action="store_true",
                        help="Optional marked-road filtering; OFF by default; needs a saved polygon")
    parser.add_argument("--stream-port", type=int, default=None,
                        help="Expose annotated MJPEG and configured zones for local dashboard, e.g. 8765")
    parser.add_argument("--stream-host", default="127.0.0.1",
                        help="Stream HTTP bind address; default loopback only (no authentication)")
    args = parser.parse_args()
    try:
        run(args.port, args.preview_only, args.no_api, args.dwell, args.weights,
            args.zone_file, args.ppe_weights, args.proximity_mm,
            args.record, args.retry_seconds, args.predictive, args.sharp_zone,
            args.motion_debug, args.road_file, args.road_filter,
            args.stream_port, args.stream_host)
    except KeyboardInterrupt:
        print("[EXIT] Interrupted by user")


if __name__ == "__main__":
    main()
