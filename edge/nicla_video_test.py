"""Analyse a downloaded MP4 with the same predictor used by the Nicla.

Unlike filming a monitor through the 320x240 grayscale Nicla, this test uses
the video's original colour frames. It doesn't control hardware or upload events.
Run from repo root:
    python -m edge.nicla_video_test --video data/pedestrians.mp4 --motion-debug
"""
import argparse
import math
from pathlib import Path

from .nicla_motion import PredictiveMotionMonitor
from .nicla_recording import TimedFrameRecorder


def frame_step(source_fps, analysis_fps):
    """Return a simple sampling stride; reject unreasonable FPS values."""
    if not (math.isfinite(source_fps) and source_fps > 0):
        source_fps = 30.0
    if not (math.isfinite(analysis_fps) and analysis_fps > 0):
        raise ValueError("analysis-fps must be positive and finite")
    return max(1, int(round(source_fps / analysis_fps)))


def run(video, weights="yolov8n.pt", conf=0.25, analysis_fps=8.0,
        motion_debug=False, save=None):
    # Keep OpenCV and YOLO optional so unit tests can run in lightweight CI.
    import cv2
    from ultralytics import YOLO

    if not 0 < conf <= 1:
        raise ValueError("conf must be in (0, 1]")
    source = Path(video)
    if not source.is_file():
        raise FileNotFoundError(f"Download the video to a local MP4 first: {source}")
    if save and source.resolve() == Path(save).resolve():
        raise ValueError("Output must be different from input video")

    capture = cv2.VideoCapture(str(source))
    if not capture.isOpened():
        raise RuntimeError("Could not open input video: " + str(source))
    writer = None
    recorder = None
    preview = "SiteGuardian: Car-person video diagnostics (Q to quit)"
    try:
        fps = float(capture.get(cv2.CAP_PROP_FPS))
        if not math.isfinite(fps) or fps <= 0:
            fps = 30.0
            print("[VIDEO] Source FPS unavailable; assuming 30")
        stride = frame_step(fps, analysis_fps)
        print(f"[VIDEO] {source} | source {fps:.1f} FPS | processing every {stride} frames")
        print("[VIDEO] Full-colour frames; no Nicla connected, no LED/API events.")
        print("[MODEL] Loading:", weights)
        model = YOLO(weights)
        monitor = PredictiveMotionMonitor()
        cv2.namedWindow(preview, cv2.WINDOW_NORMAL)
        cv2.resizeWindow(preview, 960, 540)
        index = -1
        last_log_at = -1.5
        previous_active = False
        warning_count = 0
        while True:
            ok, frame = capture.read()
            if not ok:
                break
            index += 1
            if index % stride:
                continue
            timestamp = index / fps
            height, width = frame.shape[:2]
            result = model.track(
                frame, persist=True, tracker="bytetrack.yaml",
                conf=conf, classes=[0, 2], imgsz=640, verbose=False
            )[0]
            boxes = result.boxes
            items = []
            coordinates = boxes.xyxy.cpu().numpy()
            classes = boxes.cls.cpu().numpy()
            track_ids = (boxes.id.cpu().numpy() if boxes.id is not None
                         else [None] * len(coordinates))
            for bbox, class_id, track_id in zip(coordinates, classes, track_ids):
                category = int(class_id)
                ident = int(track_id) if track_id is not None else None
                xyxy = tuple(int(v) for v in bbox)
                if ident is not None:
                    items.append((ident, category, xyxy))
                x1, y1, x2, y2 = xyxy
                tint = (60, 210, 80) if category == 0 else (0, 170, 255)
                label = "PERSON" if category == 0 else "CAR"
                cv2.rectangle(frame, (x1, y1), (x2, y2), tint, 2)
                cv2.putText(frame, f"{label} #{ident if ident is not None else '?'}",
                            (x1, max(22, y1 - 5)), cv2.FONT_HERSHEY_SIMPLEX,
                            0.65, tint, 2)
            alerts = monitor.update(items, timestamp, width, height)
            for alert in alerts:
                if alert.hazard_type == "vehicle_approaching_person":
                    warning_count += 1
                    print(f"[HAZARD] vehicle_approaching_person | "
                          f"CAR {alert.source_id} -> PERSON {alert.target_id} | "
                          f"projected {alert.seconds_ahead:.2f}s")
            active = any(
                alert.hazard_type == "vehicle_approaching_person"
                for alert in monitor.active
            )
            if active and not previous_active:
                print(f"[ALERT] APPROACH WARNING at clip time {timestamp:.1f}s")
            previous_active = active

            # Project tracked motion for the same one-second interval as the
            # live Nicla overlay. Pixel paths aren't real-world trajectories.
            for ident, track in monitor.tracks.items():
                if track.samples < 2 or timestamp - track.timestamp > 0.2:
                    continue
                if abs(track.vx) + abs(track.vy) < 0.025:
                    continue
                start = (int(track.xy[0] * width), int(track.xy[1] * height))
                end = (max(0, min(width - 1, int((track.xy[0] + track.vx) * width))),
                       max(0, min(height - 1, int((track.xy[1] + track.vy) * height))))
                tint = (0, 170, 255) if track.class_id == 2 else (255, 220, 0)
                cv2.arrowedLine(frame, start, end, tint, 2, tipLength=0.2)

            if motion_debug:
                text = monitor.debug_summary
                if timestamp - last_log_at >= 1.5:
                    print(f"[MOTION DEBUG] clip {timestamp:.1f}s | {text}")
                    last_log_at = timestamp
                cv2.rectangle(frame, (0, height - 55), (width, height),
                              (0, 0, 0), -1)
                cv2.putText(frame, text[:100], (12, height - 19),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.52, (0, 255, 255), 2)
            if active:
                cv2.putText(frame, "PREDICTED VEHICLE/PERSON APPROACH",
                            (12, 45), cv2.FONT_HERSHEY_SIMPLEX, 0.9, (0, 0, 255), 3)
            cv2.putText(frame, f"VIDEO {timestamp:.1f}s | Q quit",
                        (12, 24 if not active else 80),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.65, (255, 255, 255), 2)
            if save:
                if recorder is None:
                    target = Path(save)
                    target.parent.mkdir(parents=True, exist_ok=True)
                    writer = cv2.VideoWriter(
                        str(target), cv2.VideoWriter_fourcc(*"mp4v"),
                        10.0, (width, height)
                    )
                    if not writer.isOpened():
                        raise RuntimeError("Cannot create MP4 output: " + str(target))
                    recorder = TimedFrameRecorder(writer, fps=10.0)
                recorder.write(frame, timestamp)
            cv2.imshow(preview, frame)
            if cv2.waitKey(1) & 0xFF in (ord("q"), ord("Q")):
                break
        print(f"[VIDEO] Finished. Confirmed car-person warnings: {warning_count}")
        if warning_count == 0:
            print("[VIDEO] No approach event met the criteria. "
                  "Read [MOTION DEBUG] for whether detection/tracking or paths failed.")
    finally:
        capture.release()
        if recorder is not None:
            recorder.release()
            print(f"[VIDEO] Saved annotated output to {save}")
        elif writer is not None:
            writer.release()
        cv2.destroyAllWindows()


def main():
    parser = argparse.ArgumentParser(
        description="Test SiteGuardian tracked vehicle/person convergence on a video file"
    )
    parser.add_argument("--video", required=True, help="Path to a downloaded MP4")
    parser.add_argument("--weights", default="yolov8n.pt", help="Person/car COCO YOLO model")
    parser.add_argument("--conf", type=float, default=0.25,
                        help="Detection threshold for offline analysis (default 0.25)")
    parser.add_argument("--analysis-fps", type=float, default=8.0,
                        help="Approximate rate for processing source video frames")
    parser.add_argument("--motion-debug", action="store_true",
                        help="Show and print reasons car/person prediction is not firing")
    parser.add_argument("--save", help="Optional annotated output MP4")
    args = parser.parse_args()
    run(args.video, weights=args.weights, conf=args.conf,
        analysis_fps=args.analysis_fps, motion_debug=args.motion_debug,
        save=args.save)


if __name__ == "__main__":
    main()
