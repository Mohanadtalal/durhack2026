# Clear all camera boxes

The SiteGuardian **Reset all boxes** button is available beneath the live
camera on the **Overview** and **Camera** pages. It requires operator
confirmation. The laptop's loopback-only preview server accepts a bounded
POST control and the Nicla capture thread executes the operation.

Reset removes:
- All previously saved danger-zone polygons from `data/nicla_zones.json`.
- All saved road-zone polygons from `data/nicla_road_conflicts.json`.
- Any unfinished zone drawing and active manual ROI / CSRT tracker.
- The visual camera overlays, including bounding boxes, until **Show
  detection boxes** is selected.

Reset does **not** erase saved incidents or snapshots, stop AI inference,
disable hardware warning lights, or change Nicla firmware. If an AI hazard
remains present, detection and warning continue even when visual overlays
are hidden. Display the warnings prominently in the main dashboard.

A successful control request means **queued**, not yet executed. The
camera loop executes it on the next frame. Status includes `boxes_visible`.
If the edge process is stopped or USB disconnected, a request cannot take
effect until the loop resumes; do not claim boxes were cleared merely because
HTTP returned 202.

Only a locally bound preview server can accept control calls. Requests
require the `X-SiteGuardian-Control` header and restrict browser Origins
to the configured local dashboard origins. If the preview is exposed to
another machine, controls remain disabled; this prototype has no remote
authentication. Run only on trusted networks.

The camera dashboard requires `--stream-port 8765` and
`VITE_CAMERA_URL=http://127.0.0.1:8765/stream.mjpg`.
