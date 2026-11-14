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

## Interactive restricted-zone editor (laptop only)

The camera preview now supports a user-defined **polygon** restricted zone.
No changes to Nicla firmware or to other developers' backend/frontend are needed.

1. Run `python -m edge.nicla_detector --port COM9 --no-api --dwell 5`
   from the repository root (change COM9 if Windows assigns another port).
2. Click the camera preview window and press **E** to enter new-zone mode.
3. **Left-click** 3–12 corners around your chosen danger area. A yellow line
   and numbered yellow points show the pending polygon.
4. Press **U** to undo the last corner, **S** to save/activate the polygon,
   or **C** to cancel editing without changing the active zone.
5. Press **R** to remove the saved polygon and restore the default rectangle.
   Press **Q** to quit the camera window.

The saved file is `data/nicla_zone.json` on your **Windows laptop**, not on
the Nicla USB drive. The `data/` directory is Git-ignored; the choice survives
restarts without affecting teammates. The polygon uses normalized coordinates,
so it also scales to different image sizes.

During editing, the previously active zone continues to control detection.
Saving/resetting restarts occupancy/dwell tracking for the newly selected zone.
The program rejects fewer than three corners, duplicate vertices, very small
or self-intersecting polygons; errors appear in the terminal. This is a
visual heuristic and must not be relied on as a real-world safety boundary.

You can test editing **without YOLO** using:
`python -m edge.nicla_detector --port COM9 --preview-only`
The drawn region persists, and you can then run `--no-api --dwell 5`.

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
