# Shared API contract

Development base: http://127.0.0.1:8000

- `GET /api/health` -> `{"status":"ok","storage_mode":"memory" | "mongodb"}`
- `POST /api/events` -> store event; idempotent for same event_id.
- `GET /api/events?limit=30` -> recent events, newest first.
- `GET /api/stats` -> counts by hazard, zone, severity (up to latest 200).
- `POST /api/insights` -> Gemini analysis of latest 100 events, requires API key.

## POST /api/events sample
```json
{
  "event_id": "9d71ca4c-16aa-4372-a815-82d4753bac40",
  "timestamp": "2026-11-14T14:00:00Z",
  "source_id": "camera-01",
  "zone_id": "cutting-station-a",
  "hazard_type": "zone_entry",
  "severity": "warning",
  "description": "Person entered the configured virtual restricted area",
  "metadata": {"demo": true}
}
```

Event types available in this scaffold: `zone_entry` and `prolonged_exposure`. Other event types can be introduced later without changing the common envelope.

Errors: 422 bad input, 503 configured MongoDB/Gemini service unavailable, 502 Gemini request failed, 404 no incidents to analyse. The API is unauthenticated and must not be exposed to public internet.
