# Nicla Vision: OpenMV + USB laptop bridge

Your Nicla Vision has an onboard camera and RGB LED. This branch uses **USB**, not Wi-Fi.
The board sends raw 320x240 grayscale frames to your laptop (no JPEG compression); laptop YOLO detects people, and sends
4-byte `warn`/`safe` commands to control the onboard red LED.

## Step 1 — Verify the board
1. Install [OpenMV IDE](https://openmv.io/pages/download).
2. Connect the Nicla with a data-capable **Micro USB** cable.
3. Connect OpenMV IDE and run the HelloWorld/camera example. Confirm preview works.
4. Open `hardware/nicla_vision/main.py` in OpenMV IDE, and use its **Save Open Script to OpenMV Cam** option to save it as `main.py` *on the board*.
5. Stop and disconnect OpenMV IDE from the board; reset the Nicla. **Do not run the USB script from the IDE** while the laptop tries to use its COM port.
6. Find the board port under Device Manager > Ports, or run `python -m serial.tools.list_ports -v`.

The OpenMV USB VCP snapshot example explicitly documents this save-as-main.py workflow:
https://book.openmv.cc/en/example/50-Arduino-Boards/Nicla-Vision/50-Board-Control/usb_vcp.html

## Step 2 — Camera preview
From repository root with Python venv active:

```powershell
pip install -r backend/requirements.txt -r edge/requirements-vision.txt -r edge/requirements-hardware.txt
python -m edge.nicla_detector --port COM5 --preview-only
```

Replace COM5 with your device port. The camera preview should appear. Press `q` to quit.

## Interactive **multiple** restricted zones (laptop only)

The camera starts with **no restricted zones**, and every new zone you save
is **added to** your existing zones, rather than replacing them. Up to 12
polygon zones can be configured, each with 3–12 corners. Each zone gets
independent entry and prolonged-exposure events, and the Nicla's LED lights
red whenever a person is detected in **any** zone.

1. Run `python -m edge.nicla_detector --port COM9 --no-api --dwell 5`
   from the project directory. OpenMV IDE must be closed.
2. Click the camera window and press **E** to start **adding** a new zone.
3. **Left-click** its polygon corners. Press **U** to undo a corner.
4. Press **S** to save and activate this zone. Existing zones stay on screen.
5. Repeat **E → clicks → S** to add another polygon. The outlines are labelled
   ZONE 1, ZONE 2, etc. Each occupied zone turns red independently.
6. Press **C** to cancel only the unfinished zone.
7. Press **R** to **delete all zones**, including their saved configuration.
   The view then contains no rectangles/polygons. Press **Q** to quit.

Zones are persisted on the Windows laptop to **`data/nicla_zones.json`**
(version 2), not to the Nicla storage drive. This is intentionally a new
filename: the previous single-zone file `data/nicla_zone.json` is ignored
and **does not bring back the old default rectangle**. Fresh installs show
no zones. Saved zones reload on later runs until you press R to clear them.
The `data/` directory is git-ignored, so configurations stay local.

The current active zones continue detecting people while you draw another.
The user-defined polygons are image-space approximations, not calibrated
real-world safety boundaries. The USB firmware does not need changing.

The backend keeps its existing event shape but sets `zone_id` to
`nicla-zone-1`, `nicla-zone-2`, etc. for individual polygon events.

You can edit zones without a model using:
`python -m edge.nicla_detector --port COM9 --preview-only`

## Step 3 — Detect a person and flash red LED

```powershell
python -m edge.nicla_detector --port COM5 --no-api --dwell 5
```

This runs a laptop YOLO detector. It updates the Nicla's red LED and prints
zone-entry and dwell events, without requiring the backend.

## Step 4 — Send to teammates' API
Start backend separately using `python -m uvicorn backend.app.main:app --reload`,
then run `python -m edge.nicla_detector --port COM5 --dwell 5`. The existing
shared incident schema is unchanged.

## Important limitations

- Only person/virtual-zone/dwell detection, NOT helmets/sharp objects yet.
- Person foot position is approximated from the image; this is NOT a real distance measurement.
- OpenMV firmware APIs differ by version. Report any errors rather than wiring an unknown component.
- This red LED command depends on the laptop; independent offline board-side protection is a later feature.
- The first YOLO run can download weights; the camera is limited to QVGA images.
- Never demonstrate with actual hazards or use in a real construction site.

## Fix for firmware 5.0.1: "OSError: Compression Failed!"

Your COM9 PING succeeds but the earlier JPEG encoder failed. The updated
`main.py` uses **raw grayscale transfer** using the four-byte command `raw0`.
It sends a four-byte little-endian payload length (76800), then 76800 pixel
bytes. The laptop builds a 320x240 image using NumPy and converts it to BGR
for OpenCV and YOLO. This bypasses JPEG entirely.

### Replace old firmware safely
1. Download the latest `feat/edge-vision-nicla` branch on Windows with
   `git pull --ff-only origin feat/edge-vision-nicla`.
2. Ensure OpenMV IDE and camera test program are **closed**.
3. In File Explorer confirm that `D:` is the Nicla Vision storage drive;
   its drive letter may change. Keep a backup of the current `main.py`.
4. Copy `hardware/nicla_vision/main.py` from your clone **onto the Nicla's
   USB drive**, overwriting the existing `main.py`. You can instead use
   OpenMV IDE's "Save Open Script to OpenMV Cam" if that works.
5. Safely **Eject** the Nicla USB storage drive to flush pending writes.
   Unplug and reconnect the board to cold-boot the new program.
6. Close OpenMV IDE and run
   `python -m edge.nicla_detector --port COM9 --preview-only`.
7. To test the USB protocol alone, you can use the Windows one-liner
   `python -c "from edge.nicla_usb import NiclaUSB; n=NiclaUSB.connect('COM9'); print(n.ping()); print(len(n.snapshot_gray())); n.close()"`
   and expect `True` then `76800`.

If `raw0` still fails, leave the flash filesystem intact and capture the
exact terminal output. Do not reflash or erase the board just to troubleshoot.

## Next Developer 1 features: distance sensor, PPE weights, recording and USB retry

The normal command **continues to work with existing Nicla firmware**:
```powershell
python -m edge.nicla_detector --port COM9 --no-api --dwell 5
```
All features below are opt-in. Use a fresh working branch for testing before
merging. OpenMV IDE must be closed whenever Python is connected to COM9.

### 1. Record a demo MP4 — no firmware changes

```powershell
python -m edge.nicla_detector --port COM9 --no-api --dwell 5 --record data/siteguardian_demo.mp4
```

An annotated MP4 is saved after quitting with Q. The file remains on the
laptop and is Git-ignored. MP4 files still use 10 FPS, but timestamps now pace
the recording: at 4–5 FPS capture/inference speed, previous frames repeat to
preserve approximate real-time playback duration. If camera capture exceeds
10 FPS, extra input frames are skipped. This does **not** increase detection
FPS or interpolate motion. USB-disconnected time is excluded, and unexpected
stalls are limited to 2 seconds of frozen video. On quit, the terminal prints
the output duration and number of recorded frames.
Obtain permission before recording identifiable people.
The physical Nicla LED is not visible in the video unless filmed separately.

### 2. Auto-reconnect after USB dropouts

The laptop retries connecting every 2 seconds if serial open/transfer fails,
and resets hazard states before processing resumes. You may choose
`--retry-seconds 3`. Keep the window open; press Q to exit or Ctrl+C.
If the laptop or cable stops working, the system **cannot provide a reliable
safety warning**; this is a demo convenience, not resilience certification.

### 3. Forward ToF proximity warning — requires updating board `main.py`

The Arduino Nicla Vision's onboard VL53L1CB measures **one forward distance**,
typically up to 4 m, with a narrow field of view. It does **not** measure
the distance to each YOLO bounding box and must not be described as
person-to-machinery distance.

Official Nicla/OpenMV reference:
https://docs.arduino.cc/tutorials/nicla-vision/user-manual

**Before updating your working board**:
1. Save a copy of the current working `D:\\main.py` on the laptop.
2. Verify D: is still your Nicla drive.
3. Copy this branch's `hardware/nicla_vision/main.py` to `D:\\main.py`.
4. Safely eject D:, unplug/replug Nicla, and close OpenMV IDE.

The updated firmware adds the four-byte command `dist`, returning a 32-bit
unsigned little-endian millimetre reading; `0xFFFFFFFF` means unavailable.
It lazily loads the sensor so the existing `raw0` stream is unchanged.

Test the sensor protocol first:
```powershell
python -c "from edge.nicla_usb import NiclaUSB; n=NiclaUSB.connect('COM9'); print('PING', n.ping()); print('DISTANCE_MM', n.distance_mm()); n.close()"
```
A number such as 650 means an object about 650 mm in front of the sensor.
`None` means sensor not ready/unavailable, not that the area is clear.
Then run:
```powershell
python -m edge.nicla_detector --port COM9 --no-api --proximity-mm 800
```
Two consecutive readings at or below 800 mm activate a forward-proximity
alert; two readings above 800 mm clear it. The LED is red when any zone, PPE
(if enabled), or ToF alert is active.

### 4. Optional PPE model (helmet and safety vest)

The default `yolov8n.pt` COCO model detects people but **not missing PPE**.
The `--ppe-weights` flag loads **separate** YOLO weights with explicit
`no_helmet` and/or `no_vest` classes, including aliases `no-hardhat`
and `no-safety vest`. If neither class exists, startup rejects the model.
No absence is inferred solely because a helmet/vest was not detected.

One publicly available, independently maintained research model for
evaluation (its benchmark is model-author-reported; not safety-certified):
https://huggingface.co/constructelligence/construction-site-safety-hazards

Download its optional 22.6 MB PyTorch `.pt` weights into a local
Git-ignored folder:
```powershell
python -m pip install huggingface_hub
python -c "from huggingface_hub import hf_hub_download; print(hf_hub_download(repo_id='constructelligence/construction-site-safety-hazards', filename='buildvision-hazards-v0.3.pt', local_dir='data/models'))"
python -m edge.nicla_detector --port COM9 --no-api --dwell 5 --ppe-weights data/models/buildvision-hazards-v0.3.pt
```

This third-party model uses AGPL-3.0 weights. Check licensing if the project
will be distributed commercially, and test with consented demo images. The
320x240 grayscale Nicla feed may miss or misclassify PPE, especially when
small or occluded. No real safety decisions should rely on these detections.

### Combined demonstration

After testing each independent mode:
```powershell
python -m edge.nicla_detector --port COM9 --no-api --dwell 5 --proximity-mm 800 --ppe-weights data/models/buildvision-hazards-v0.3.pt --record data/siteguardian_demo.mp4
```

### Diagnosis for PING works but DIST times out

The board script now supports `vers` and returns a four-byte version marker
`SG03`. This distinguishes a freshly loaded firmware from older scripts that
respond `PONG` but ignore `dist`.

After copying this updated feature-branch `main.py` onto the Nicla USB drive,
safely eject the drive, **unplug and reconnect the USB cable**, keep OpenMV IDE
closed, and run (with your venv active):

```powershell
python -c "from edge.nicla_usb import NiclaUSB; n=NiclaUSB.connect('COM9'); print('PING:',n.ping()); print('VERSION:',n.firmware_version()); print('DISTANCE:',n.distance_mm()); n.close()"
```

Expect `PING: True`, `VERSION: b'SG03'`, and either a distance
in millimetres or `DISTANCE: None` if the ToF sensor is unavailable.

If VERSION times out, the running board script is still old or did not
reload. If the marker appears but DIST fails, capture the full error and
isolate the ToF code without changing the known-good raw camera path.

## Predictive motion hazards (optional, experimental)

This mode attempts **early warnings before image-space paths meet**. It uses
Ultralytics ByteTrack persistent track IDs and 2D movement history; it
requires a **fixed/mounted camera** and works without any firmware changes.

### Case A: Car moving toward a person

```powershell
python -m edge.nicla_detector --port COM9 --no-api --predictive
```

The default person YOLO detects COCO class 0 (person) and class 2 (car).
ByteTrack assigns IDs such as `PERSON #2` and `CAR #5`. After at least two
consecutive consistent approaching predictions, the overlay warns
`APPROACH: CAR 5 -> PERSON 2` and activates the red Nicla LED.
The terminal prints `vehicle_approaching_person`.
Stationary cars and vehicles moving away are ignored by the prediction logic.

This is a **screen-plane path-convergence heuristic** using box bottom-centres,
not physically calibrated time-to-collision, 3D velocity or a collision
probability. Camera shake, object scale changes and perspective may create
incorrect warnings, and small/toy cars may not be recognised by COCO YOLO.

### Case B: Person moving toward a manually marked sharp hazard

You must manually locate a harmless **sharp-object stand-in** (such as a
cardboard sign or foam prop) by creating a zone with **E → clicks → S**.
Do not use actual sharp or dangerous objects during tests.

```powershell
python -m edge.nicla_detector --port COM9 --no-api --predictive --sharp-zone 1
```

This designates saved zone 1 as the place where an operator identified a
potential sharp hazard. Other zones can be marked with repeated
`--sharp-zone 2` arguments. You may draw the zone after starting the
program. The program predicts when the person's box-footpoint trajectory
moves toward that region, shows
`APPROACH: PERSON 2 -> SHARP ZONE 1`, and emits
`person_approaching_marked_sharp_zone` once confirmed.

**Important: the current program does NOT automatically recognise all sharp
objects or distinguish backward walking from forward/sideways movement.**
It warns on movement *toward a manually marked hazard*. Actual backward
motion classification needs a separately validated pose/orientation system
and sufficiently clear frames. Do not demonstrate this as a verified
`walking backward` classifier.

You can combine prediction with PPE and ToF and record an annotated demo:

```powershell
python -m edge.nicla_detector --port COM9 --no-api --predictive --sharp-zone 1 --proximity-mm 800 --ppe-weights data/models/buildvision-hazards-v0.3.pt --record data/predictive_demo.mp4
```

The predicted hazards use the existing event shape, with the corresponding
camera-track IDs and `screen_plane_prediction: true` metadata. Events can
be sent to the backend by removing `--no-api` after integration testing.

**Safety:** Never stage a real vehicle approaching a person or use a sharp
object to test this. Use prerecorded consented footage or harmless props.
This is a hackathon proof of concept, not a tested collision-avoidance
system or emergency alarm.

### Predictive overlay

The Nicla preview draws yellow motion arrows on people and orange arrows on
cars. An active approaching-car warning adds a red line between the tracked
car and person. Arrows show a one-second **screen-space extrapolation**;
they do not convey real-world distance or verified collision time.

### Diagnose why `vehicle_approaching_person` did not trigger

Run with the optional on-screen and terminal diagnostics:

```powershell
python -m edge.nicla_detector --port COM9 --no-api --predictive --motion-debug
```

The yellow `[MOTION DEBUG]` summary reports tracked person/car counts
and the primary reason a prediction has not fired:

- `NO CAR DETECTED/TRACKED`: YOLO or ByteTrack cannot identify the car.
- `NO PERSON DETECTED/TRACKED`: person detection/tracking failed.
- `WAITING FOR STABLE TRACK IDS`: needs consecutive frames with consistent IDs.
- `CAR NOT MOVING TOWARD PERSON`: car is stationary or moving away in image coordinates.
- `APPROACH OUTSIDE 2 SECOND HORIZON`: projected closest approach occurs too far in the future.
- `PROJECTED PATHS TOO FAR APART`: paths do not converge closely enough.
- `APPROACH CANDIDATE - CONFIRMING`: a possible approach is being debounced.
- `VEHICLE WARNING ACTIVE`: warning was confirmed and LED should be active.

A video of traffic and pedestrians does not necessarily contain a near-path
approach meeting the heuristic. Filming an existing video on a monitor with
Nicla's grayscale 320×240 camera further reduces detection quality. Before
changing sensitivity, **capture the debug output** to determine the issue.

### Direct MP4 test when a car-person warning does not appear

If the Nicla sees `PEOPLE 3 | CARS 0` repeatedly while filming a screen,
analyse the **original colour video directly**. This uses the same
`PredictiveMotionMonitor` as the live Nicla path, but bypasses the
320x240 grayscale camera and USB transport.

1. Download the source MP4 (for example from Pexels) into `data/pedestrians.mp4`.
2. With the same Python virtual environment and dependencies:

```powershell
python -m edge.nicla_video_test --video data/pedestrians.mp4 --motion-debug
```

Optional: keep an annotated video of the prediction:

```powershell
python -m edge.nicla_video_test --video data/pedestrians.mp4 --motion-debug --save data/analysed_pedestrians.mp4
```

The script processes source **video timestamps**, rather than wall clock,
and samples approximately 8 colour frames per source second by default.
It displays person/car tracks, movement arrows, and the same diagnostics
as `--motion-debug`. It reports the number of **confirmed** approach
warnings, if any, at completion.

This script is an offline debugging convenience. It does not require a
connected Nicla and does **not** send red-LED warnings or events to the
backend. Even with full-resolution input, busy crossing footage may have
**no** paths meeting the approach criteria. It is not evidence that
an actual collision was imminent.
