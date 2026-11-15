# Camera freezes around detections — nonblocking alert delivery

**What changed:** the camera/detection loop no longer waits for the incident
HTTP POST, snapshot upload or retrying a stale offline queue. The edge host
uses `AsyncEventReporter` (one background thread, bounded queue) to send
incident records and snapshots. Physical Nicla USB LED commands and the
existing warning rules remain on the camera thread and are unchanged.

**Try it:** use the same Nicla command you already run, but add
`--profile-latency`. Example (replace COM9 with your existing port):

```powershell
python -m edge.nicla_detector --port COM9 --stream-port 8765 --profile-latency
```

Avoid `--no-api` when testing website incidents; use it temporarily to
identify whether networking contributes to a freeze. The timed diagnostic
prints only frames slower than 200 ms, roughly once per second, with stage
durations:

- `usb`: raw frame read (USB serial/camera acquisition)
- `analysis`: AI model, region rules and other processing
- `led`: Nicla USB LED and optional UNO Q state updates
- `events`: JPEG evidence encoding + queuing (not HTTP)
- `render`: UI drawing and local MJPEG preview publishing

**Interpretation:** If `events` is low but `analysis` is high, inspect
YOLO inference speed and tracker settings. If `led` spikes exactly on exit,
look at USB serial latency and unplug/reconnect issues. If `usb` is high,
check the cable/port and the Nicla's frame acquisition. If `render` is high,
test without `--stream-port` or recording to isolate image encoding.

**Delivery reliability:** To avoid frame stalls, new events briefly wait in a
bounded in-memory queue. The worker performs disk staging and preserves
failed HTTP deliveries in the existing JSONL + JPEG retry queue. It also
retries idle pending incidents. The buffer can overflow under a prolonged
outage and unprocessed events can be lost on abrupt termination; the terminal
reports any overflow or shutdown timeout. This hackathon prototype is not a
safety-critical alarm or durable incident recorder.

Hardware commands to `hardware/nicla_vision/main.py` are unchanged. The
feature is still USB-connected; Wi-Fi has not been added by this fix.
