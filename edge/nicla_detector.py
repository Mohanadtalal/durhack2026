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
import os
import time
from datetime import datetime, timezone
from pathlib import Path
from uuid import uuid4

from .auto_hazards import HazardMonitor, find_hazards, parse_labels
from .async_events import AsyncEventReporter
from .camera_controls import clear_saved_camera_boxes
from .manual_tracking import create_manual_tracker, update_manual_trackers
from .nicla_extra_rules import (
    PPE_HAZARDS, ProximityAlert, extract_ppe_hazards, supported_ppe_classes,
)
from .nicla_geometry import DebouncedOccupancy
from .nicla_recording import TimedFrameRecorder
from .nicla_motion import PredictiveMotionMonitor
from .nicla_usb import NiclaProtocolError, NiclaUSB
from .uno_q_warning import UnoQWarning
from .preview_server import PreviewServer, zones_for_editor
from .zone_editor import DEFAULT_ZONE_FILE, ZoneEditor, person_in_polygon
from .zone_rules import ZoneMonitor


def run(port, preview_only=False, no_api=False, dwell=8.0, weights="yolov8n.pt",
        zone_file=DEFAULT_ZONE_FILE, ppe_weights=None, proximity_mm=None,
        record_path=None, retry_seconds=2.0, predictive=False, sharp_zone_ids=(),
        motion_debug=False, road_file="data/nicla_road_conflicts.json",
        road_filter=False, stream_port=None, stream_host="127.0.0.1",
        uno_q_url=None, profile_latency=False, auto_hazards=False,
        hazard_weights=None, hazard_labels="knife", hazard_confidence=0.45):
    import cv2
    import numpy as np

    if retry_seconds < 0.5:
        raise ValueError("retry_seconds must be at least 0.5")
    if preview_only and ppe_weights:
        raise ValueError("Remove --preview-only when using a PPE model.")
    if preview_only and auto_hazards:
        raise ValueError("Automatic object recognition requires a YOLO model; remove --preview-only.")
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
    hazard_model = None
    hazard_monitor = HazardMonitor() if auto_hazards else None
    wanted_hazards = parse_labels(hazard_labels) if auto_hazards else ()
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

    if auto_hazards:
        # COCO person/vehicle weights cannot recognise knives. Use explicit
        # open-vocabulary weights or a separately trained knife detector.
        if hazard_weights:
            from ultralytics import YOLO
            hazard_model = YOLO(hazard_weights)
            available = {str(v).strip().casefold()
                         for v in hazard_model.names.values()} if isinstance(
                             hazard_model.names, dict) else {
                                 str(v).strip().casefold() for v in hazard_model.names}
            missing = set(wanted_hazards) - available
            if missing:
                raise ValueError(
                    f"Hazard weights lack requested labels {sorted(missing)}. "
                    "Train a detector with these classes or omit --hazard-weights "
                    "to use YOLO-World."
                )
            print("[AUTO HAZARD] Custom knife-capable model:", hazard_weights)
        else:
            from ultralytics import YOLOWorld
            hazard_model = YOLOWorld("yolov8s-worldv2.pt")
            hazard_model.set_classes(list(wanted_hazards))
            print("[AUTO HAZARD] Open-vocabulary model; labels:", wanted_hazards)
        print("[AUTO HAZARD] Automatic recognition enabled; no ROI/T key needed.")
        print("[AUTO HAZARD] Detection is experimental; NEVER rely on it for safety.")

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
    window = "SiteGuardian: Nicla Vision" #name of camera window that appears on screen 
    frame_size = [320, 240]


    running = True #controls camera loop continution 
    preview = None # variable holds the streaming server 

    reporter = AsyncEventReporter() if not no_api else None
    last_latency_log = 0.0
    uno_q = UnoQWarning(uno_q_url) if uno_q_url else None
    if uno_q is not None:
        print("[UNO Q] Mirroring Nicla warnings to", uno_q.base_url)


    # Operator-selected object tracking (T adds a box; B removes all boxes).
    trackers = []
    tracking_margin = 30

    #function runs when you interact with camera window with mous e
    def on_mouse(event, x, y, flags, userdata):
        if event == cv2.EVENT_LBUTTONDOWN:
            active_editor.add_corner(x, y, frame_size[0], frame_size[1])

    def report(hazard_type, zone_id, severity="warning", metadata=None, snapshot_jpeg=None):
        print("[HAZARD]", hazard_type, "|", zone_id)
        if no_api:
            return
        accepted = reporter.submit({
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
        }, snapshot_jpeg=snapshot_jpeg)
        if not accepted:
            print('[EVENT BUFFER FULL] Alert could not be queued:', hazard_type)

    print("Opening Nicla Vision:", port, "| close OpenMV IDE first")
    print("Keys: E danger zone, L road zone, left-click corners, S save, U undo, C cancel,")
    print("R clear danger zones, K clear road zones, T add tracker, B clear trackers, Q quit.")
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
                    if uno_q is not None:
                        uno_q.set_state(False)
                    print("[USB] Connected and responding on", port)
                    warning_active = False
                    last_distance_poll = 0.0


                    # Camera controls are consumed here, never from the HTTP worker.
                    # This keeps ZoneEditor, tracker and video state single-threaded.
                    #keeps camera tracking system running
                    while running:
                        if preview is not None:
                            for control in preview.take_controls():
                                if control == "reset-boxes":
                                    try:
                                        clear_saved_camera_boxes(
                                            editor, road_editor, occupancies, monitors, preview
                                        )
                                    except OSError as exc:
                                        print("[BOX RESET] Could not remove saved zones:", exc)
                                        continue
                                    trackers.clear()
                                    active_editor = editor
                                    sharp_zone_ids.clear()  # Old marked-sharp zone IDs no longer exist.
                                    preview.hub.set_boxes_visible(False)
                                    print("[BOX RESET] Saved zones and manual box cleared. "
                                          "Detection and warning rules still running.")
                                elif control == "show-boxes":
                                    preview.hub.set_boxes_visible(True)
                                    print("[BOX RESET] Live detection overlays visible again.")
                        frame_started_at = time.perf_counter()
                        raw = nicla.snapshot_gray()
                        capture_finished_at = time.perf_counter()
                        gray = np.frombuffer(raw, dtype=np.uint8).reshape((240, 320))
                        frame = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
                        height, width = frame.shape[:2]



                        frame_size[:] = [width, height]
                        regions = editor.pixels(width, height)
                        road_regions = road_editor.pixels(width, height)
                        inference_frame = frame.copy()
                        now = time.monotonic()
                        events = []

                        # Track every operator-selected box on every frame, and
                        # do not draw boxes on input sent to the AI models.
                        manual_boxes, lost_count = update_manual_trackers(
                            trackers, inference_frame
                        )
                        for x, y, w, h in manual_boxes:
                            x1 = max(0, x - tracking_margin)
                            y1 = max(0, y - tracking_margin)
                            x2 = min(width - 1, x + w + tracking_margin)
                            y2 = min(height - 1, y + h + tracking_margin)
                            cv2.rectangle(frame, (x1, y1), (x2, y2), (0, 0, 255), 2)
                        if lost_count:
                            print("[TRACK] Lost", lost_count,
                                  "object(s); active:", len(trackers))


                        # Recognise danger objects automatically in every frame.
                        # ByteTrack assigns IDs so boxes follow moving detected objects.
                        if hazard_model is not None:
                            hazard_result = hazard_model.track(
                                inference_frame, persist=True, tracker="bytetrack.yaml",
                                conf=hazard_confidence, verbose=False,
                            )[0]
                            hazard_boxes = hazard_result.boxes
                            matches = []
                            if hazard_boxes is not None:
                                xyxy = hazard_boxes.xyxy.cpu().numpy()
                                kinds = hazard_boxes.cls.cpu().numpy()
                                scores = hazard_boxes.conf.cpu().numpy()
                                ids = (hazard_boxes.id.cpu().numpy()
                                       if hazard_boxes.id is not None
                                       else [None] * len(xyxy))
                                matches = find_hazards(
                                    hazard_model.names,
                                    zip(kinds, scores, xyxy, ids),
                                    wanted_hazards, hazard_confidence,
                                )
                            new_episode = hazard_monitor.update(matches)
                            for hit in matches:
                                x1, y1, x2, y2 = hit.box
                                cv2.rectangle(frame, (x1, y1), (x2, y2),
                                              (0, 0, 255), 2)
                                suffix = f" #{hit.track_id}" if hit.track_id is not None else ""
                                cv2.putText(
                                    frame, f"SHARP OBJECT {hit.label}{suffix} {hit.confidence:.2f}",
                                    (x1, max(18, y1 - 5)),
                                    cv2.FONT_HERSHEY_SIMPLEX, .42, (0, 0, 255), 1,
                                )
                            if new_episode:
                                primary = max(matches, key=lambda x: x.confidence)
                                events.append((
                                    "sharp_object_detected", "nicla-camera-view", "warning",
                                    {"object_label": primary.label,
                                     "confidence": round(primary.confidence, 3),
                                     "track_id": primary.track_id,
                                     "detection_mode": ("custom_weights" if hazard_weights
                                                        else "yolo_world_zero_shot"),
                                     "automatically_detected": True,
                                     "not_safety_certified": True},
                                ))

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
                        sharp_object_alert = hazard_monitor.active if hazard_monitor else False
                        should_warn = (in_zone or ppe_alert or tof_alert
                                       or predicted_alert or sharp_object_alert)
                        analysis_finished_at = time.perf_counter()
                        if uno_q is not None:
                            # Nonblocking: latest state wins; periodic sync survives UNO Q restarts.
                            uno_q.set_state(should_warn)
                        if should_warn != warning_active:
                            nicla.set_warning(should_warn)
                            warning_active = should_warn
                            print("[LOCAL LED]", "RED - hazard present" if should_warn else "OFF - clear")
                        warning_finished_at = time.perf_counter()

                        # Capture the *same* camera frame that caused the alert.
                        # Encode once even if multiple incident rules fire together.
                        evidence_jpg = None
                        if events and not no_api:
                            ok, encoded = cv2.imencode(
                                ".jpg", inference_frame,
                                [int(cv2.IMWRITE_JPEG_QUALITY), 82]
                            )
                            if ok:
                                evidence_jpg = encoded.tobytes()
                            else:
                                print("[EVIDENCE] Could not encode alert frame")
                        for event_type, zone_id, severity, metadata in events:
                            report(event_type, zone_id, severity, metadata,
                                   snapshot_jpeg=evidence_jpg)
                        reporting_finished_at = time.perf_counter()

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

                        # Clearing boxes hides all visual overlays, not the AI itself.
                        # The original frame is used for preview and recording.
                        if preview is not None and not preview.hub.boxes_visible():
                            frame = inference_frame.copy()

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
                        if profile_latency:
                            finished_at = time.perf_counter()
                            frame_ms = (finished_at - frame_started_at) * 1000
                            if frame_ms >= 200 and finished_at - last_latency_log >= 1.0:
                                last_latency_log = finished_at
                                print(
                                    "[LATENCY] total={:.0f}ms usb={:.0f}ms analysis={:.0f}ms "
                                    "led={:.0f}ms events={:.0f}ms render={:.0f}ms count={} "
                                    "warning={}".format(
                                        frame_ms,
                                        (capture_finished_at - frame_started_at) * 1000,
                                        (analysis_finished_at - capture_finished_at) * 1000,
                                        (warning_finished_at - analysis_finished_at) * 1000,
                                        (reporting_finished_at - warning_finished_at) * 1000,
                                        (finished_at - reporting_finished_at) * 1000,
                                        len(events), should_warn,
                                    )
                                )
                        if key in (ord("q"), ord("Q")):
                            running = False
                            break
                        if key in (ord("t"), ord("T")):
                            # Selecting an ROI temporarily pauses the video.
                            # Press Enter to accept a box or Escape to cancel.
                            selected = cv2.selectROI(window, frame, False, False)
                            if selected[2] > 0 and selected[3] > 0:
                                try:
                                    tracker = create_manual_tracker(cv2)
                                    initialized = tracker.init(inference_frame, selected)
                                    if initialized is False:
                                        print("[TRACK] Could not initialise the selected box")
                                    else:
                                        trackers.append(tracker)
                                        print("[TRACK] Objects tracked:", len(trackers))
                                except (RuntimeError, cv2.error) as exc:
                                    print("[TRACK] Could not add selected object:", exc)
                        if key in (ord("b"), ord("B")):
                            trackers.clear()
                            print("[TRACK] All manually selected objects cleared.")


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
                # Mirror Nicla reset on disconnect; unknown camera state is not safety assurance.
                if uno_q is not None:
                    uno_q.set_state(False)
                warning_active = False
                trackers.clear()  # Stale boxes cannot follow a new camera session.
                if hazard_monitor is not None:
                    hazard_monitor.reset()
                    # Do not reuse tracker IDs across separate camera connections.
                    if hazard_model is not None and getattr(hazard_model, "predictor", None):
                        for tracker in getattr(hazard_model.predictor, "trackers", []):
                            tracker.reset()
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
        if reporter is not None:
            reporter.close()
        if uno_q is not None:
            uno_q.close()
        if preview is not None:
            preview.close()
        if recording is not None:
            recording.release()
            print(f"[RECORD] Saved {recording.duration_seconds:.1f}s of video "
                  f"({recording.frames_written} frames) to {record_path}")
        cv2.destroyAllWindows()


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
    parser.add_argument("--uno-q-url", default=os.getenv("UNO_Q_URL", ""),
                        help="Optional UNO Q App Lab URL via ADB: http://127.0.0.1:7000")
    parser.add_argument("--profile-latency", action="store_true",
                        help="Log slow frames by stage (USB, detection, LED, reporting, preview)")
    parser.add_argument("--auto-hazards", action="store_true",
                        help="Automatically recognise/track sharp objects (experimental YOLO-World)")
    parser.add_argument("--hazard-weights",
                        help="Optional custom YOLO weights trained explicitly on requested hazard labels")
    parser.add_argument("--hazard-labels", default="knife",
                        help="Comma-separated detection classes, e.g. knife,scissors,saw")
    parser.add_argument("--hazard-confidence", type=float, default=0.45,
                        help="Minimum sharp-object model confidence (0 to 1)")
    args = parser.parse_args()
    try:
        run(args.port, args.preview_only, args.no_api, args.dwell, args.weights,
            args.zone_file, args.ppe_weights, args.proximity_mm,
            args.record, args.retry_seconds, args.predictive, args.sharp_zone,
            args.motion_debug, args.road_file, args.road_filter,
            args.stream_port, args.stream_host, args.uno_q_url,
            args.profile_latency, args.auto_hazards, args.hazard_weights,
            args.hazard_labels, args.hazard_confidence)
    except KeyboardInterrupt:
        print("[EXIT] Interrupted by user")


if __name__ == "__main__":
    main()
