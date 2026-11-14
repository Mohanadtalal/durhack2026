"""Nicla Vision USB capture + laptop YOLO + local warning + incident API.

Camera-only preview:
    python -m edge.nicla_detector --port COM5 --preview-only

Detection and red LED, no backend required:
    python -m edge.nicla_detector --port COM5 --no-api --dwell 5

Normal integration:
    python -m edge.nicla_detector --port COM5 --dwell 5
"""
import argparse
import time
from datetime import datetime, timezone
from uuid import uuid4

from .nicla_geometry import DebouncedOccupancy
from .zone_editor import DEFAULT_ZONE_FILE, ZoneEditor, person_in_polygon
from .nicla_usb import NiclaUSB
from .zone_rules import ZoneMonitor


def run(port, preview_only=False, no_api=False, dwell=8.0, weights="yolov8n.pt", zone_file=DEFAULT_ZONE_FILE):
    import cv2
    import numpy as np
    from .client import send_event, flush_pending

    model = None
    if not preview_only:
        from ultralytics import YOLO
        print("Loading person-detection model:", weights)
        model = YOLO(weights)

    editor = ZoneEditor(zone_file)
    # Each zone tracks entry/dwell separately; a person in ANY zone triggers the LED.
    monitors = [ZoneMonitor(dwell_seconds=dwell) for _ in editor.zones]
    occupancies = [DebouncedOccupancy(required_frames=2) for _ in editor.zones]
    warning_active = False
    window_name = "SiteGuardian: Nicla Vision"
    frame_size = [320, 240]

    def on_mouse(event, x, y, flags, userdata):
        if event == cv2.EVENT_LBUTTONDOWN:
            editor.add_corner(x, y, frame_size[0], frame_size[1])
    t0 = time.monotonic()
    nframes = 0
    print("Opening Nicla Vision", port, "(disconnect OpenMV IDE first)")
    print("Zone controls: E=add zone, click 3+ corners, U=undo, S=save, C=cancel, R=clear ALL, Q=quit.")
    print("Zone file on laptop:", editor.path, "| loaded", len(editor.zones), "zones")
    try:
        with NiclaUSB.connect(port) as nicla:
            if not nicla.ping():
                raise RuntimeError("Nicla did not respond to PING. Install hardware/nicla_vision/main.py as main.py and reboot.")
            nicla.set_warning(False, force=True)
            cv2.namedWindow(window_name, cv2.WINDOW_AUTOSIZE)
            cv2.setMouseCallback(window_name, on_mouse)
            while True:
                raw = nicla.snapshot_gray()
                gray = np.frombuffer(raw, dtype=np.uint8).reshape((240, 320))
                frame = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
                h, w = frame.shape[:2]
                frame_size[:] = [w, h]
                regions = editor.pixels(w, h)
                people = []
                if model is not None:
                    result = model.predict(frame, conf=0.45, classes=[0], verbose=False)[0]
                    people = [
                        tuple(int(v) for v in box)
                        for box in result.boxes.xyxy.cpu().numpy()
                    ]
                    for ax, ay, bx, by in people:
                        cv2.rectangle(frame, (ax,ay), (bx,by), (50,220,120), 2)

                if len(regions) != len(occupancies):
                    raise RuntimeError("Zone configuration changed outside the editor.")
                now = time.monotonic()
                active_zones = []
                for i, region in enumerate(regions):
                    observed = person_in_polygon(people, region)
                    occupancies[i].update(observed)
                    if occupancies[i].inside:
                        active_zones.append(i + 1)

                # Local warning is sent before potentially slow HTTP reporting.
                any_inside = bool(active_zones)
                if any_inside != warning_active:
                    nicla.set_warning(any_inside)
                    warning_active = any_inside
                    print("[LOCAL LED]", "RED - zone occupied" if any_inside else "OFF - zone clear")

                for i, monitor in enumerate(monitors):
                    for event_type in monitor.update(occupancies[i].inside, now):
                        zone_number = i + 1
                        print("[HAZARD]", event_type, "| zone", zone_number)
                        if not no_api:
                            send_event({
                                "event_id": str(uuid4()),
                                "timestamp": datetime.now(timezone.utc).isoformat(),
                                "source_id": "nicla-vision-01",
                                "zone_id": f"nicla-zone-{zone_number}",
                                "hazard_type": event_type,
                                "severity": "high" if event_type == "prolonged_exposure" else "warning",
                                "description": f"Nicla zone {zone_number}: " + event_type.replace("_", " "),
                                "metadata": {
                                    "camera": "nicla_vision",
                                    "zone_index": zone_number,
                                    "virtual_zone": True,
                                    "distance_calibrated": False,
                                    "simulated": False,
                                },
                            })

                for i, region in enumerate(regions):
                    color = (0, 0, 255) if occupancies[i].inside else (0, 190, 70)
                    cv2.polylines(frame, [np.array(region, dtype=np.int32)], True, color, 2)
                    label_x = min(x for x, y in region)
                    label_y = min(y for x, y in region)
                    cv2.putText(frame, f"ZONE {i + 1}", (max(4, label_x), max(36, label_y - 7)),
                                cv2.FONT_HERSHEY_SIMPLEX, .47, color, 2)
                if not regions:
                    cv2.putText(frame, "NO ZONES - press E to add one", (5, 38),
                                cv2.FONT_HERSHEY_SIMPLEX, .42, (0, 255, 255), 1)

                # Editing does not disturb the active zone until S saves it.
                if editor.editing:
                    draft = editor.draft_pixels(w, h)
                    if len(draft) >= 2:
                        cv2.polylines(frame, [np.array(draft, dtype=np.int32)], False, (0, 255, 255), 2)
                    for index, (x, y) in enumerate(draft):
                        cv2.circle(frame, (x, y), 4, (0, 255, 255), -1)
                        cv2.putText(frame, str(index + 1), (x + 5, y - 5),
                                    cv2.FONT_HERSHEY_SIMPLEX, .35, (0, 255, 255), 1)
                    cv2.putText(frame, f"DRAW: {len(draft)} points | S save U undo C cancel", (4, 29),
                                cv2.FONT_HERSHEY_SIMPLEX, .34, (0, 255, 255), 1)
                cv2.putText(frame, f"{len(regions)} zones | E add | S save | U undo | C cancel | R clear | Q quit", (4, 14),
                            cv2.FONT_HERSHEY_SIMPLEX, .31, (255, 255, 255), 1)
                nframes += 1
                fps = nframes / max(.001, time.monotonic() - t0)
                cv2.putText(frame, f"Nicla USB | {fps:.1f} fps", (5, h - 8),
                            cv2.FONT_HERSHEY_SIMPLEX, .45, (255, 255, 255), 1)
                cv2.imshow(window_name, frame)
                key = cv2.waitKey(1) & 0xFF
                if key in (ord("q"), ord("Q")):
                    break
                if key in (ord("e"), ord("E")):
                    editor.begin()
                    print("[ZONE] Adding zone", len(editor.zones) + 1, "- left click 3+ corners; S to save.")
                elif key in (ord("u"), ord("U")):
                    editor.undo()
                elif key in (ord("c"), ord("C")):
                    editor.cancel()
                    print("[ZONE] Edit cancelled; all existing zones retained.")
                elif key in (ord("s"), ord("S")) and editor.editing:
                    try:
                        saved = editor.save()
                    except (OSError, ValueError) as exc:
                        print("[ZONE] Not saved:", exc)
                    else:
                        if saved:
                            # Add tracking only for the new zone; existing alerts continue.
                            occupancies.append(DebouncedOccupancy(required_frames=2))
                            monitors.append(ZoneMonitor(dwell_seconds=dwell))
                            print("[ZONE] Added zone", len(editor.zones), "| total:", len(editor.zones))
                elif key in (ord("r"), ord("R")):
                    try:
                        editor.reset()
                    except OSError as exc:
                        print("[ZONE] Reset failed:", exc)
                    else:
                        nicla.set_warning(False, force=True)
                        warning_active = False
                        occupancies.clear()
                        monitors.clear()
                        print("[ZONE] Cleared all zones. Camera now starts with no zones.")
    finally:
        cv2.destroyAllWindows()
        if not no_api:
            try:
                flush_pending()
            except Exception as exc:
                print("[QUEUE] Pending events remain unsent:", exc)


def main():
    parser = argparse.ArgumentParser(description="Nicla Vision USB person/zone detector")
    parser.add_argument("--port", required=True, help="Windows COM port, e.g. COM5")
    parser.add_argument("--preview-only", action="store_true", help="Camera preview without YOLO")
    parser.add_argument("--no-api", action="store_true", help="No HTTP events; test local LED only")
    parser.add_argument("--dwell", type=float, default=8.0, help="Seconds to trigger prolonged exposure")
    parser.add_argument("--weights", default="yolov8n.pt", help="YOLO person-detection model")
    parser.add_argument("--zone-file", default=str(DEFAULT_ZONE_FILE), help="Local saved multi-zone configuration")
    args = parser.parse_args()
    try:
        run(args.port, args.preview_only, args.no_api, args.dwell, args.weights, args.zone_file)
    except KeyboardInterrupt:
        print("Interrupted.")


if __name__ == "__main__":
    main()
