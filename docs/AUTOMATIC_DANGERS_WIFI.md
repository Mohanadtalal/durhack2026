# SiteGuardian: automatic sharp-object tracking + wall-camera Wi-Fi roadmap

## What is implemented in this branch

The optional `--auto-hazards` mode runs a **second, knife-capable YOLO
model**, recognises sharp objects without pressing T, assigns moving
ByteTrack IDs and places boxes around detections automatically. When a knife
is recognised, it adds `sharp_object_detected` to the usual incident queue,
and immediately asks for the same red LED/UNO Q indicator used by other
hazards. After four consecutive missed frames, that warning clears.

**Important:** The standard COCO `yolov8n.pt` does NOT recognise knives.
The optional YOLO-World model uses text labels and makes mistakes, especially
with small tools or the current 320x240 **grayscale** USB feed. It is a
prototype; it must not be used as a real safety control.

The manual T/CSRT tracking route has been removed; ordinary E/S fixed hazard
zones remain available independently and are NOT necessary for knives.

### Try the current, working USB Nicla + UNO Q demo

Start the `SiteGuardian Warning` App Lab app, forward its HTTP port over USB
and ensure both USB cables are connected:

```powershell
$adb = "$env:LOCALAPPDATA\Arduino15\packages\arduino\tools\adb\32.0.0\adb.exe"
& $adb forward tcp:7000 tcp:7000
Invoke-RestMethod http://127.0.0.1:7000/status
$env:UNO_Q_URL = "http://127.0.0.1:7000"
python -m edge.nicla_detector --port COM9 --auto-hazards --hazard-labels knife --predictive --stream-port 8765
```

First startup may download `yolov8s-worldv2.pt`; an internet connection
is needed for this one-time download. The model runs on the **Windows laptop**
for this test, not yet on the UNO Q.

Point the Nicla at an **inert blunt prop or a printed picture** in a safe
test environment. The display should show automatically labelled red boxes
when the model recognises a knife. When the model recognises the prop, the
Nicla LED and the UNO Q indicator should both activate. Failure to recognise
a prop is possible and is **not** evidence that the scene is safe.

For a trained knife-specific detector instead of YOLO-World, provide a
model containing a `knife` class explicitly:

```powershell
python -m edge.nicla_detector --port COM9 --auto-hazards --hazard-weights models/knife.pt --hazard-labels knife
```

For additional types, `--hazard-labels knife,scissors,saw` is supported
with YOLO-World; custom weights must have the requested class names.
Use `--hazard-confidence 0.55` to raise the recognition confidence cutoff.

Automated tests:

```powershell
python -m pytest edge/tests/test_auto_hazards.py edge/tests/test_uno_q_warning.py -q
```

## Wireless camera hardware: Nicla Wi-Fi → UNO Q Wi-Fi

This is a **separate hardware phase**. The Nicla has a native 2.4-GHz
Wi-Fi interface, and UNO Q runs Debian Linux with dual-band Wi-Fi. We
include `hardware/nicla_vision/wifi_mjpeg.py`, an OpenMV/MicroPython
RGB-color MJPEG streamer. It streams a camera feed; it is **not** yet
integrated with the existing `NiclaUSB` detector or tested on this board.

1. Configure both devices on the same **private, secured 2.4-GHz network**
   with LAN client-to-client traffic enabled. Managed campus Wi-Fi may block
   device-to-device access.
2. In OpenMV IDE, connect Nicla Vision over USB and **Stop** any
   running script. Open `hardware/nicla_vision/wifi_mjpeg.py` (from this
   branch), fill in the two `WIFI_SSID` / `WIFI_PASSWORD` placeholders
   in the editor on your own laptop. **Never put your real credentials
   in Git, screenshots, or chat.**
3. Click **Run** to test the script *temporarily*. **Do not click
   "Save to OpenMV Cam" or name it `main.py`** at this stage. This is
   only a runtime test; power-cycling the Nicla restores the existing
   `/flash/main.py` USB firmware. The Nicla prints its private IPv4
   address and `MJPEG camera ready at .../stream.mjpg`.
   The sketch uses OpenMV v5 `csi.CSI` and `to_jpeg`; JPEG streaming
   on this Nicla still needs a hardware test and may fail if memory or
   encoding is unavailable. If so, note the full console error and
   restore the original firmware before proceeding.
4. On the same private Wi-Fi, open
   `http://<NICLA_IP>:8080/stream.mjpg` in a browser to test video.
5. Confirm the **UNO Q** (not only the laptop) can receive a real JPEG
   frame over Wi-Fi. From Windows PowerShell, while UNO Q is attached
   over USB for provisioning:
   ```powershell
   & $adb push hardware/uno_q_warning/python/check_wifi_camera.py /tmp/check_wifi_camera.py
   & $adb shell "python3 /tmp/check_wifi_camera.py http://<NICLA_IP>:8080/stream.mjpg"
   ```
   Replace `<NICLA_IP>` with the Nicla's actual private-network IP address.
   Successful output says `UNO Q RECEIVED Nicla Wi-Fi camera JPEG`.
   This is **transport-only verification**; the UNO Q still needs a
   deployed image decoder, lightweight detector and tracking runtime
   before autonomous knife recognition can run without a laptop.

**This firmware replaces the current USB command firmware:** do not upload
it if you want to test the existing COM9 Nicla detector immediately. To
return to the USB camera demo, restore `hardware/nicla_vision/main.py`.

## Goal: truly standalone wall-mounted SiteGuardian

```text
Nicla Vision camera ---- private 2.4-GHz Wi-Fi ----> Arduino UNO Q
  USB power                                          Linux vision inference
                                                     Arduino matrix + local warning
                                                     Wi-Fi status/dashboard relay
```

To make this a **laptop-free safety-camera prototype**, move the image
decoder, lightweight **knife-trained** inference model, tracking, and event
publisher to the UNO Q Linux environment. Prefer a small custom model
exported to a runtime supported on the UNO Q, then benchmark recognition
latency and RAM. Running desktop YOLO-World/PyTorch at useful FPS on a
2-GB UNO Q has **not been established**. Arduino App Lab has custom AI
model integrations, but its ready-made USB camera path is not a drop-in
reader for a remote Nicla MJPEG feed.

A more dependable alternative if the two boards will share one enclosure:
use a short internal USB connection from Nicla to UNO Q (with an appropriate
USB-host/PD adapter), run the camera and model on the UNO Q, and use **Wi-Fi
only for viewing status remotely**. USB-host compatibility with the Nicla's
custom serial protocol and model installation must also be tested.

Both boards still need **regulated electrical power** even if video and
alerts are wireless. Provide safe cabling, ventilation, and a protective
wall enclosure that leaves the lens unobstructed. UNO Q power specification:
USB-C 5 V up to 3 A; check the Nicla's independent supply as well.
Do not expose the unauthenticated MJPEG or Web UI to a public network.

## Current completion status

- [x] Automatic knife-capable model integration for the **laptop USB demo**.
- [x] Automatic tracker IDs, bounding boxes, incident generation, LED and UNO Q hook.
- [x] Nicla Wi-Fi streaming firmware **example added**.
- [ ] Verify automatic knife detection on real camera frames (not yet tested).
- [ ] Verify Nicla Wi-Fi MJPEG firmware on hardware (not yet tested).
- [ ] Port/benchmark automatic detection on UNO Q Linux.
- [ ] Fully standalone wireless assembly and wall-enclosure test.

Not certified for industrial hazard detection or life-safety use.


## Integration with the responsive dashboard (PR #14)

This branch now includes `main` after PR #14. The automatic knife detector
reports incidents through `AsyncEventReporter`, which stages and uploads a
JPEG snapshot **before** creating the incident record. Network I/O and
retry-queue persistence run off the video loop.

Run the combined USB demo using the camera's actual COM port:

```powershell
python -m edge.nicla_detector --port COM9 --auto-hazards --hazard-labels knife --predictive --stream-port 8765 --profile-latency
```

`--auto-hazards` loads a second model and may itself slow frames, even
though background incident delivery no longer blocks the video. The
`--profile-latency` output splits capture, analysis, LED, event encoding,
and preview rendering time. Test with the physical Nicla Vision; successful
unit tests do not establish real-time performance or knife recognition.

The Wi-Fi MJPEG file is an **alternative example only**, not a drop-in
replacement for the USB command firmware. Do not flash it over
`hardware/nicla_vision/main.py` when testing the USB detector.
