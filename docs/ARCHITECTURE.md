# SiteGuardian AI — architecture and decisions

## Data flow

```text
webcam / simulated node
   |
edge person detector -> zone rules -> LOCAL warning / Arduino
   |                              (independent of cloud)
   v
HTTP POST /api/events -> FastAPI -> MongoDB incidents
                                          |
                                          v
                               Gemini incident analysis
                                          |
                                          v
                               React dashboard / API
```

## Design contracts
- Local hazard rules must issue warnings immediately, not wait for an LLM, database or internet.
- The baseline detector checks one virtual **image-space zone** with person detection. It does NOT measure physical distances.
- Transition-based event emission: one `zone_entry` on entry; one `prolonged_exposure` when a dwell-time threshold is reached; reset on exit.
- Every event has a unique UUID; replays of an event with the same ID must not create duplicate records.
- MongoDB stores structured incident metadata; raw video and worker identities are **not** stored.
- Gemini receives a bounded set of structured history events and gives **advisory explanations**, not safety-critical decisions.
- Use independent edge processes for future multi-camera zones; offline queues allow later replay.
- A configured but unavailable MongoDB does not silently fall back to volatile memory.

## Prototype limitations
This project is not a construction-site safety system. Webcam accuracy depends on lighting, occlusion, model quality and camera geometry. Proximity, PPE, fire and fall detection require extra models and validation. Physical warning outputs require real-board tests. The API has no authentication and must run on a trusted development machine only.

## Future iterations
PPE detector; machine/object proximity with calibrated camera or depth data; obstruction and vehicle detection; independently connected edge nodes; hardware safety interlocks only with competent safety engineering review.
