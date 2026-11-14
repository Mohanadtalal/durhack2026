# Developer 3 — Gemini integration and testing

The original work by `YoussefITkmind` is preserved in Git history and
integrated with the latest `main` (including Developers 1, 2 and 4).

## Contract

The React **AI review** page calls `POST /api/insights`. FastAPI reads
up to 100 newest stored incidents and calls the Gemini service. The
service calculates verified frequencies and percentages of hazards,
zones and severities before requesting advisory prose. The API responds
with `summary`, `model`, and `events_analyzed`.

The external Gemini request deliberately includes ONLY four structured
fields: timestamp, hazard_type, zone_id and severity. Other stored
information, including event ID, source ID, description and arbitrary
metadata, is not shared. It does not operate local safety alarms.

## Validate

```powershell
pip install -r backend/requirements.txt -r backend/requirements-dev.txt
python -m pytest backend/tests edge/tests -q
```

The added tests fake Gemini (no network, billing, or API credentials).
They test statistics, prompt minimisation, the 100-incident limit,
missing-key handling, external errors and the existing FastAPI/React
insights response schema.

## Live demo (team action still required)

Set `GEMINI_API_KEY` in a local `.env` file created from
`.env.example` (never commit or share the key), optionally choose
`GEMINI_MODEL`. Leave `MONGODB_URI` empty to run with temporary
in-memory demo storage, or configure the team's private Atlas connection.

```powershell
python -m uvicorn backend.app.main:app --reload
```

In another terminal:

```powershell
cd frontend
npm install
npm run dev
```

Generate harmless practice incidents through the frontend or
`python -m edge.demo`; click **AI review** and request insights.
When no events exist the endpoint returns HTTP 404; without a configured
key it returns HTTP 503. A working real Gemini key, access and quota
must be verified by the team separately.

**Prototype only.** AI recommendations are human-reviewed and never
authoritative instructions for physical construction-site safety.
