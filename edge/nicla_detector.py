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

from .nicla_geometry import DebouncedOccupancy, person_in_zone, zone_from_fractions
from .nicla_usb import NiclaUSB
from .zone_rules import ZoneMonitor


def run(port, preview_only=False, no_api=False, dwell=8.0, weights="yolov8n.pt"):
    import cv2
    import numpy as np
    from .client import send_event, flush_pending

    model = None
    if not preview_only:
        from ultralytics import YOLO
        print("Loading person-detection model:", weights)
        model = YOLO(weights)

    zone_monitor = ZoneMonitor(dwell_seconds=dwell)
    occupancy = DebouncedOccupancy(required_frames=2)
    t0 = time.monotonic()
    nframes = 0
    print("Opening Nicla Vision", port, "(disconnect OpenMV IDE first)")
    print("Press q in the preview window to exit.")
    try:
        with NiclaUSB.connect(port) as nicla:
            if not nicla.ping():
                raise RuntimeError("Nicla did not respond to PING. Install hardware/nicla_vision/main.py as main.py and reboot.")
            nicla.set_warning(False, force=True)
            while True:
                raw = nicla.snapshot_gray()
                gray = np.frombuffer(raw, dtype=np.uint8).reshape((240, 320))
                frame = cv2.cvtColor(gray, cv2.COLOR_GRAY2BGR)
                h, w = frame.shape[:2]
                region = zone_from_fractions(w, h)
                people = []
                if model is not None:
                    result = model.predict(frame, conf=0.45, classes=[0], verbose=False)[0]
                    people = [
                        tuple(int(v) for v in box)
                        for box in result.boxes.xyxy.cpu().numpy()
                    ]
                    for ax, ay, bx, by in people:
                        cv2.rectangle(frame, (ax,ay), (bx,by), (50,220,120), 2)

                currently_observed = person_in_zone(people, region)
                previous_state = occupancy.inside
                inside = occupancy.update(currently_observed)

                # Local alarm output comes BEFORE any potentially slow HTTP work.
                if inside != previous_state:
                    nicla.set_warning(inside)
                    print("[LOCAL LED]", "RED - zone occupied" if inside else "OFF - zone clear")

                for event_type in zone_monitor.update(inside, time.monotonic()):
                    print("[HAZARD]", event_type)
                    if not no_api:
                        send_event({
                            "event_id": str(uuid4()),
                            "timestamp": datetime.now(timezone.utc).isoformat(),
                            "source_id": "nicla-vision-01",
                            "zone_id": "cutting-station-a",
                            "hazard_type": event_type,
                            "severity": "high" if event_type == "prolonged_exposure" else "warning",
                            "description": "Nicla virtual zone: " + event_type.replace("_", " "),
                            "metadata": {
                                "camera": "nicla_vision",
                                "virtual_zone": True,
                                "distance_calibrated": False,
                                "simulated": False,
                            },
                        })

                x1,y1,x2,y2 = region
                color = (0,0,255) if inside else (0,190,70)
                cv2.rectangle(frame, (x1,y1), (x2,y2), color, 2)
                cv2.putText(frame, "RESTRICTED DEMO ZONE", (max(4,x1), max(18,y1-8)),
                            cv2.FONT_HERSHEY_SIMPLEX, .47, color, 2)
                nframes += 1
                fps = nframes / max(.001, time.monotonic()-t0)
                cv2.putText(frame, f"Nicla USB | {fps:.1f} fps", (5,h-8),
                            cv2.FONT_HERSHEY_SIMPLEX, .45, (255,255,255), 1)
                cv2.imshow("SiteGuardian: Nicla Vision", frame)
                if cv2.waitKey(1) & 0xFF == ord("q"):
                    break
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
    args = parser.parse_args()
    try:
        run(args.port, args.preview_only, args.no_api, args.dwell, args.weights)
    except KeyboardInterrupt:
        print("Interrupted.")


if __name__ == "__main__":
    main()
