"""Optional single-zone YOLO camera demo. Run from repo root: python -m edge.camera

Requires OpenCV+Ultralytics. NOT distance measurement or certified hazard detection.
Uses the bottom-center of person boxes as a simple virtual-zone contact point.
"""
import os
import time
from datetime import datetime, timezone
from uuid import uuid4
from dotenv import load_dotenv
from .client import send_event, flush_pending
from .zone_rules import ZoneMonitor

load_dotenv()

def main():
    import cv2
    from ultralytics import YOLO

    board = None
    port = os.getenv("ARDUINO_PORT", "").strip()
    if port:
        try:
            import serial
            board = serial.Serial(port, 9600, timeout=1)
            time.sleep(2)
        except Exception as exc:
            print("Arduino unavailable; using console alarm:", exc)
    camera = cv2.VideoCapture(int(os.getenv("CAMERA_INDEX", "0")))
    if not camera.isOpened():
        raise RuntimeError("Camera unavailable. Check CAMERA_INDEX.")
    model = YOLO("yolov8n.pt")
    monitor = ZoneMonitor(float(os.getenv("DWELL_SECONDS", "8")))
    previous_inside = False

    try:
        while True:
            success, frame = camera.read()
            if not success:
                break
            height, width = frame.shape[:2]
            x1,y1,x2,y2 = (int(width*.35),int(height*.20),int(width*.80),int(height*.90))
            detection = model.predict(frame, conf=.45, classes=[0], verbose=False)[0]
            inside = False
            for raw in detection.boxes.xyxy.cpu().numpy():
                xa,ya,xb,yb = [int(p) for p in raw]
                foot = ((xa+xb)//2, yb)
                inside = inside or (x1 <= foot[0] <= x2 and y1 <= foot[1] <= y2)
                cv2.rectangle(frame,(xa,ya),(xb,yb),(40,200,130),2)

            # Local warning happens BEFORE network delivery.
            if inside != previous_inside:
                print("[LOCAL WARNING]", "ZONE BREACH" if inside else "ZONE CLEAR")
                if board:
                    board.write(b"ALERT\n" if inside else b"CLEAR\n")
                previous_inside = inside

            for kind in monitor.update(inside, time.monotonic()):
                send_event({
                    "event_id": str(uuid4()),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "source_id": "webcam-01",
                    "zone_id": "cutting-station-a",
                    "hazard_type": kind,
                    "severity": "high" if kind == "prolonged_exposure" else "warning",
                    "description": "Webcam virtual zone: " + kind.replace("_"," "),
                    "metadata": {"virtual_zone":True,"distance_calibrated":False},
                })
            color = (0,0,255) if inside else (0,210,80)
            cv2.rectangle(frame,(x1,y1),(x2,y2),color,3)
            cv2.putText(frame,"RESTRICTED DEMO ZONE",(x1,max(25,y1-12)),
                        cv2.FONT_HERSHEY_SIMPLEX,.6,color,2)
            cv2.imshow("SiteGuardian AI - webcam demo",frame)
            if cv2.waitKey(1) & 0xFF == ord("q"):
                break
    finally:
        camera.release()
        cv2.destroyAllWindows()
        if board:
            board.write(b"CLEAR\n")
            board.close()
        flush_pending()

if __name__ == "__main__":
    main()
