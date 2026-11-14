// All backend access lives here. If the API contract changes, fix it in one place.
const BASE = import.meta.env.VITE_API_BASE || 'http://127.0.0.1:8000'

async function request(path, opts) {
  const r = await fetch(BASE + path, opts)
  if (!r.ok) {
    const body = await r.json().catch(() => ({}))
    throw new Error(body.detail || 'HTTP ' + r.status)
  }
  return r.json()
}

// Only allow http(s) or same-site paths for evidence images (blocks javascript: URLs).
function safeImageUrl(value) {
  if (typeof value !== 'string') return null
  if (value.startsWith('/')) return BASE + value
  if (/^https?:\/\//i.test(value)) return value
  return null
}

export function normalizeIncident(e) {
  const md = e.metadata || {}
  return {
    ...e,
    ts: new Date(e.timestamp).getTime(),
    // Anything flagged by the simulator/demo scripts must never look like a live detection.
    simulated: Boolean(md.simulated || md.demo),
    snapshot: safeImageUrl(md.snapshot_url),
    confidence: typeof md.confidence === 'number' ? md.confidence : null,
  }
}

export const getHealth = () => request('/api/health')
export const getEvents = async (limit = 200) =>
  (await request('/api/events?limit=' + limit)).map(normalizeIncident)
export const postEvent = (body) =>
  request('/api/events', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify(body),
  })
export const runInsights = () => request('/api/insights', { method: 'POST' })
