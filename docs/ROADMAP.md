# 22-hour development plan

| Hours | Deliverable |
|---|---|
| 0–2 | Project architecture and team GitHub clone |
| 2–6 | Local zone engine and webcam integration |
| 6–8 | Hazard warning and repeat/false-alarm handling |
| 8–11 | MongoDB persistence and API |
| 11–13 | Gemini historical-analysis integration |
| 13–16 | Live dashboard integration |
| 16–19 | Physical Arduino alarm or second edge agent |
| 19–22 | Full tests, integration, offline demo fallback, pitch |

## Definition of done
- Crossing staged virtual zone -> exactly one immediate local warning and one entry event.
- Staying in it -> one timed event; no frame-by-frame alert flood.
- Leaving and returning -> a fresh entry event.
- MongoDB stores one record per incident UUID, including replay attempts.
- Dashboard displays actual stored events; memory-mode is visibly labeled.
- Gemini insight uses actual history and gives evidence-based **suggestions for review**.
- If API is disconnected, local warning still operates and events queue to disk.
- A clear and truthful demo distinguishes simulated from webcam events.
