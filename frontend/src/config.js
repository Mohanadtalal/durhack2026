// Severity ladder matches backend Literal["info","warning","high","critical"].
export const SEVERITY = {
  info:     { label: 'Info',     rank: 0 },
  warning:  { label: 'Warning',  rank: 1 },
  high:     { label: 'High',     rank: 2 },
  critical: { label: 'Critical', rank: 3 },
}
export const SEVERITY_ORDER = ['critical', 'high', 'warning', 'info']

// Camera polygon IDs are provided by edge/preview_server.py at runtime.
// A hard-coded map must never present invented work areas as safe.

export const WINDOWS = [
  { id: 'all', label: 'All time', ms: Infinity },
  { id: '15m', label: 'Last 15 min', ms: 15 * 60e3 },
  { id: '1h',  label: 'Last hour', ms: 60 * 60e3 },
  { id: '24h', label: 'Last 24 h', ms: 24 * 60 * 60e3 },
]

// A zone shows its live status from events this recent; older events still count in totals.
export const ACTIVE_WINDOW_MS = 15 * 60e3

export const friendly = (t) =>
  String(t || '').replaceAll('_', ' ').replaceAll('-', ' ').replace(/\b\w/g, (c) => c.toUpperCase())

export function timeAgo(ts, now = Date.now()) {
  const s = Math.max(0, Math.round((now - ts) / 1000))
  if (s < 10) return 'just now'
  if (s < 60) return s + ' s ago'
  if (s < 3600) return Math.floor(s / 60) + ' min ago'
  if (s < 86400) return Math.floor(s / 3600) + ' h ago'
  return Math.floor(s / 86400) + ' d ago'
}

export function topSeverity(list) {
  let best = null
  for (const e of list) if (!best || SEVERITY[e.severity]?.rank > SEVERITY[best]?.rank) best = e.severity
  return best
}

const TITLES = {
  zone_entry: 'Someone entered a restricted area',
  prolonged_exposure: 'Someone stayed in a restricted area too long',
}
export const plainTitle = (e) => TITLES[e.hazard_type] || friendly(e.hazard_type)
export const STATE_WORD = { info: 'Minor', warning: 'Warning', high: 'High alert', critical: 'Critical' }
