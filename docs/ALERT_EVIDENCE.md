# Alert evidence and dashboard

The Nicla Vision firmware and existing USB protocol do not change for this feature.

When the Nicla **edge detector** reports a camera incident (with API reporting
enabled), it JPEG-encodes the actual frame that triggered the rule. The edge
client stores a temporary copy in `data/pending_snapshots`, then:

1. Uploads raw JPEG to `POST /api/snapshots/{event_id}` (max 2 MB).
2. Receives a verified `snapshot_url` for `GET /api/snapshots/{event_id}.jpg`.
3. Sends the incident to `POST /api/events` with `metadata.snapshot_url` and
   `metadata.snapshot_status=available`.
4. Deletes its temporary file only after both operations succeed.

If uploading fails or the API is unreachable, the **event and its image**
remain in `data/pending_events.jsonl` and `data/pending_snapshots` and are
retried on subsequent sends. Until that retry succeeds the incident is not
published to the dashboard; the local Arduino LED/UNO Q warning is independent
and continues operating. The queue is not a realtime alerting guarantee.

If encoding or staging a frame fails, the incident is still sent without a
broken URL and with an explicit `snapshot_status`. Pre-existing and simulated
incidents may also have no snapshot; the UI displays a placeholder.

The API stores verified JPEGs atomically in `data/snapshots` (configurable
using `SITEGUARDIAN_SNAPSHOT_DIR`). Keep this directory intact alongside
MongoDB; data in it is **not** inside MongoDB. Snapshots need their own backup,
retention/deletion policy, and access controls before any real-world use.

To see the UI: start the API and frontend as in the root README, run the
detector with API reporting (omit `--no-api`), then go to **Overview**. The
control centre shows the camera, recent alert thumbnails, an evidence gallery,
and the Gemini briefing divided into sections. Click an incident to open its
original evidence image.

**Privacy and security:** These endpoints have no authentication, just like
the existing prototype API. Only bind the API and preview stream to localhost
on a trusted development machine; do not expose them publicly or upload real
people's images without appropriate permission.
