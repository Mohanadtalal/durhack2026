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
