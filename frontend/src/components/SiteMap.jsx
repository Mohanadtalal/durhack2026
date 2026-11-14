import React from 'react'
import { ACTIVE_WINDOW_MS, SEVERITY, topSeverity, friendly } from '../config'

// Actual camera polygon IDs and names come from the Nicla preview service.
// Historic incident IDs still appear when the camera is unavailable, but
// are NEVER assigned fictional map coordinates.
export function zoneSummaries(events, now, cameraZones = []) {
  const known = new Set(cameraZones.map((zone) => zone.id))
  const ids = [
    ...cameraZones.map((zone) => zone.id),
    ...new Set(events.map((event) => event.zone_id).filter((id) => !known.has(id))),
  ]
  return ids.map((id) => {
    const geometry = cameraZones.find((z) => z.id === id)
    const all = events.filter((event) => event.zone_id === id)
    const recent = all.filter((event) => now - event.ts <= ACTIVE_WINDOW_MS)
    return {
      id,
      label: geometry?.label || friendly(id),
      points: geometry?.points || null,
      total: all.length,
      recent: recent.length,
      status: topSeverity(recent),
    }
  })
}

const LABELS = {
  warning: 'Warning', high: 'High alert', critical: 'Critical',
  info: 'Info',
}
const COLOUR = {
  info: '#3d82cf', warning: '#eab308',
  high: '#f97316', critical: '#e11d48',
}

function validPoints(points) {
  return Array.isArray(points) && points.length >= 3 && points.length <= 12 &&
    points.every((pair) =>
      Array.isArray(pair) && pair.length === 2 &&
      pair.every((n) => typeof n === 'number' && Number.isFinite(n) && n >= 0 && n <= 1))
}

export function SiteMap({ events, now, selectedZone = 'all', onSelectZone, cameraStatus }) {
  const geometry = Array.isArray(cameraStatus?.zones)
    ? cameraStatus.zones.filter((zone) => validPoints(zone.points))
    : []
  const summaries = zoneSummaries(events, now, geometry)
  const selected = summaries.find((s) => s.id === selectedZone)
  const mapped = summaries.filter((s) => s.points)
  const unknown = summaries.filter((s) => !s.points)
  const connected = Boolean(cameraStatus?.connected)
  const choose = (id) => onSelectZone?.(selectedZone === id ? 'all' : id)

  return (
    <div className="site-geometry">
      <div className={'zone-status ' + (connected ? 'zone-online' : 'zone-offline')}
           role="status">
        {connected ? 'Camera publishing recent frames' : 'No verified live camera feed'}
        <span>{geometry.length} configured camera {geometry.length === 1 ? 'zone' : 'zones'}</span>
      </div>
      {mapped.length > 0
        ? <svg className="camera-zone-map" viewBox="0 0 640 370" role="img"
            aria-label="Actual saved polygon areas in the camera image; schematic camera coordinates">
            <rect x="0" y="0" width="640" height="370" rx="10" fill="#14253b"/>
            {Array.from({ length: 7 }, (_, i) =>
              <line key={'v' + i} x1={20 + i * 100} y1="16" x2={20 + i * 100}
                y2="354" stroke="#ffffff14" />)}
            {Array.from({ length: 4 }, (_, i) =>
              <line key={'h' + i} x1="10" y1={20 + i * 100} x2="630"
                y2={20 + i * 100} stroke="#ffffff14" />)}
            {mapped.map((z, i) => {
              const pts = z.points.map(([x, y]) =>
                [Math.round(12 + x * 616), Math.round(14 + y * 340)])
              const fill = COLOUR[z.status] || '#2bb7a2'
              const first = pts[0]
              return <g key={z.id} role="button" tabIndex={0}
                  aria-label={z.label + ': ' +
                    (z.recent ? z.recent + ' recent incidents' : 'no recent reports')}
                  onClick={() => choose(z.id)}
                  onKeyDown={(e) => {
                    if (e.key === 'Enter' || e.key === ' ') {
                      e.preventDefault()
                      choose(z.id)
                    }
                  }}
                  style={{ cursor: 'pointer', opacity: selectedZone === 'all' || selectedZone === z.id ? 1 : .48 }}>
                  <polygon points={pts.map((p) => p.join(',')).join(' ')}
                    fill={fill} fillOpacity={selectedZone === z.id ? .4 : .22}
                    stroke={fill} strokeWidth={selectedZone === z.id ? 4 : 2}/>
                  <text x={first[0] + 7} y={Math.max(28, first[1] - 8)}
                    fill="#fff" fontSize="15" fontWeight="600">
                    {z.label.length > 23 ? 'Zone ' + (i + 1) : z.label}
                  </text>
                </g>
            })}
            <text x="16" y="354" fill="#bbc7d6" fontSize="12">
              Camera-relative geometry — not a surveyed site plan
            </text>
          </svg>
        : <div className="zone-unmapped">
            <b>No camera zone polygons available</b>
            <p>Connect the Nicla preview server and mark restricted zones in the
              camera window to see their real positions. Vehicle–worker prediction
              works separately and does not require marking zones.</p>
          </div>}
      <div className="real-zone-list">
        {summaries.map((z) =>
          <button key={z.id} type="button"
            className={'zone-list-row ' + (selectedZone === z.id ? 'zone-list-selected' : '')}
            onClick={() => choose(z.id)}>
            <span><b>{z.label}</b><small>{z.points
              ? 'Configured camera region'
              : 'Incident-only area · location not mapped'}</small></span>
            <span className="zone-activity">
              {z.recent > 0
                ? (LABELS[z.status] || 'Reported') + ' · ' + z.recent + ' recent'
                : z.total > 0 ? z.total + ' historical reports' : 'No recent reports'}
            </span>
          </button>
        )}
        {summaries.length === 0 &&
          <p className="zone-footnote">No configured areas or incident reports yet.</p>}
      </div>
      {!connected && <p className="zone-footnote">
        Camera offline or not configured. “No recent reports” never means the site is safe.
      </p>}
      {selected && <p className="zone-footnote">
        Selected: <strong>{selected.label}</strong>. {selected.total} recorded
        {selected.total === 1 ? ' incident' : ' incidents'}.
        <button className="link" onClick={() => onSelectZone?.('all')}>Clear selection</button>
      </p>}
      {unknown.length > 0 && mapped.length > 0 &&
        <p className="zone-footnote">Some recorded incidents have no known camera polygon
          and are listed separately; no position has been invented.</p>}
    </div>
  )
}
