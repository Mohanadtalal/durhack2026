# Nicla Vision: OpenMV + USB laptop bridge

Your Nicla Vision has an onboard camera and RGB LED. This branch uses **USB**, not Wi-Fi.
The board sends JPEG snapshots to your laptop; laptop YOLO detects people, and sends
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
