# Arduino UNO Q danger-sign integration (local hackathon demo)

SiteGuardian mirrors the same hazard decision that drives the **Nicla red LED**
to the **UNO Q LED-matrix danger symbol**. The UNO Q is a display only: it
does not detect people, communicate with MongoDB or drive the Nicla.

This is **not certified safety equipment** and must not be relied on to protect
workers. The local HTTP warning endpoint has **no authentication**.

## Prerequisites

- UNO Q physically connected to the **same Windows laptop** as the Nicla.
- The **SiteGuardian Warning** Arduino App Lab app is deployed and running.
  Example `sketch.ino` and `python/main.py` live in
  `hardware/uno_q_warning/`. Add the **Web UI** Brick in App Lab; its
  `app.yaml` is managed by App Lab (do not manually edit it).
- Confirm the UNO Q app responds to **POST /danger/on** and **POST
  /danger/off**. The UNO Q's built-in matrix is blue.
- Nicla Vision remains on its own COM port (example `COM9`).

## 1. Forward the UNO Q service over USB

In PowerShell, keep Arduino App Lab running and execute:

```powershell
$adb = "$env:LOCALAPPDATA\Arduino15\packages\arduino\tools\adb\32.0.0\adb.exe"
& $adb devices
& $adb forward tcp:7000 tcp:7000
Invoke-RestMethod http://127.0.0.1:7000/status
```

The status route must respond before starting camera integration. Check manual
controls:

```powershell
Invoke-RestMethod -Method Post http://127.0.0.1:7000/danger/on
Invoke-RestMethod -Method Post http://127.0.0.1:7000/danger/off
```

If the connection closes unexpectedly, ensure the App Lab app status is
**running**, not just that USB is detected:

```powershell
& $adb shell "arduino-app-cli app ps --all"
& $adb shell "ss -ltn"
```

If the UNO Q is disconnected or ADB forwarding disappears, reconnect it and
repeat the `adb forward` command. **Do not use a campus Wi-Fi address**:
the detector deliberately accepts loopback URLs only.

## 2. Start the Nicla detector with the warning display enabled

Stop the existing camera detector first. From the Git repository root:

```powershell
$env:UNO_Q_URL = "http://127.0.0.1:7000"
python -m edge.nicla_detector --port COM9 --predictive --motion-debug --stream-port 8765
```

Alternatively append `--uno-q-url http://127.0.0.1:7000` to the
detector command. Without either setting, the UNO Q integration is disabled;
existing Nicla behaviour remains unchanged. The backend and dashboard are
started exactly as before.

## 3. Verify with the physical camera

1. The app starts with the UNO Q symbol **OFF** (no hazard).
2. In the Nicla OpenCV preview, press **E**, click at least 3 points, then
   **S** to save a restricted region (or use an existing saved region).
3. Have a volunteer **safely** enter the camera's marked zone. Expect the
   Nicla red LED and UNO Q symbol to turn **ON** together.
4. Leave the region and check both warnings turn **OFF**.
5. Test resilience: while the detector is running, stop and restart the
   UNO Q App Lab app. The detector continues, logs temporary UNO Q
   unavailability, and re-sends the current warning state when the API
   returns. Re-establish ADB forwarding if its connection was lost.

The UNO Q controller uses a background thread: the camera's YOLO loop never
waits for UNO Q HTTP. It re-sends the latest state every ~2 seconds,
retries failed requests after ~1 second, and makes a bounded best-effort
OFF request on detector shutdown. ADB forwarding must still be available
and the App Lab app running for any warning to be displayed.

**Failure limitations:** If USB, the app or the network drops, the display
might retain its last state; an absent warning **does not mean an area is
safe**. On camera disconnect the detector requests OFF to mirror the Nicla's
reset behaviour, but does not claim the scene is clear. Do not deploy on
construction sites or expose the unauthenticated API publicly.

## 4. Unit checks

```powershell
python -m pytest edge/tests/test_uno_q_warning.py edge/tests/test_nicla_detector_cli.py -q
```

Automated tests mock HTTP and cannot prove actual LED behaviour. Follow the
hands-on steps above for physical verification.
