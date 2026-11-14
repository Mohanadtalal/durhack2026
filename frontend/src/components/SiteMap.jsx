import React from 'react'
import { ZONES, ACTIVE_WINDOW_MS, SEVERITY, STATE_WORD, topSeverity, friendly } from '../config'

// Status per zone: highest severity among recent events; counts include all loaded events.
export function zoneSummaries(events, now) {
  const known = new Set(ZONES.map((z) => z.id))
  const ids = [...ZONES.map((z) => z.id), ...new Set(events.map((e) => e.zone_id).filter((id) => !known.has(id)))]
  return ids.map((id) => {
    const cfg = ZONES.find((z) => z.id === id)
    const all = events.filter((e) => e.zone_id === id)
    const recent = all.filter((e) => now - e.ts <= ACTIVE_WINDOW_MS)
    return { id, cfg, label: cfg?.label || friendly(id), total: all.length, recent: recent.length, status: topSeverity(recent) }
  })
}


const LABEL = { clear: 'All clear', info: 'Minor', warning: 'Warning', high: 'High alert', critical: 'Critical' }

// Zone outlines on the plan (schematic). Keyed by zone id; `tag` is where the label sits, `dot` the status marker.
const SHAPES = {
  'cutting-station-a':   { pts: '46,44 290,42 294,170 50,176',  tag: [60, 58],  dot: [262, 150] },
  'loading-zone-b':      { pts: '330,40 590,40 594,168 334,170', tag: [344, 54], dot: [566, 146] },
  'working-at-height-c': { pts: '50,204 292,200 290,302 54,300', tag: [64, 218], dot: [264, 278] },
  'general-area-d':      { pts: '332,200 592,198 590,304 336,304', tag: [346, 214], dot: [566, 280] },
}
const KEY = [['clear', 'Clear'], ['warning', 'Warning'], ['high', 'High alert'], ['critical', 'Critical']]

export function SiteMap({ events, now, selectedZone, onSelectZone }) {
  const zones = zoneSummaries(events, now)
  const byId = Object.fromEntries(zones.map((z) => [z.id, z]))
  const other = zones.filter((z) => !z.cfg)
  const pick = (z, selected) => onSelectZone?.(selected ? 'all' : z.id)
  const sel = selectedZone !== 'all' ? byId[selectedZone] : null
  return (
    <div className="sitemap sp">
      <svg viewBox="0 0 640 370" role="img" aria-label="Plan of the site showing the status of each work area">
        <defs>
          <pattern id="sp-hard" width="9" height="9" patternUnits="userSpaceOnUse" patternTransform="rotate(45)"><line x1="0" y1="0" x2="0" y2="9" className="sp-hardline" /></pattern>
          <clipPath id="sp-clip"><rect width="640" height="370" rx="12" /></clipPath>
        </defs>
        <g clipPath="url(#sp-clip)">
          <rect width="640" height="370" className="sp-base" />
          {/* neighbouring plots and public road, kept very quiet */}
          <g className="sp-neighbour"><rect x="-6" y="-6" width="640" height="14" /><rect x="618" y="8" width="30" height="300" /><rect x="-6" y="322" width="110" height="30" /><rect x="130" y="338" width="90" height="40" /></g>
          <rect x="-6" y="334" width="660" height="40" className="sp-road" />
          <text x="304" y="357" className="sp-roadname">Site access road</text>
          {/* fence line and hard standing */}
          <polygon points="28,26 608,20 614,316 332,322 28,314" className="sp-site" />
          <polygon points="28,26 608,20 614,316 332,322 28,314" fill="url(#sp-hard)" />
          <polygon points="28,26 608,20 614,316 332,322 28,314" className="sp-fence" />
          {/* internal haul roads */}
          <path d="M292 30V312M30 188H606" className="sp-haul" />
          <path d="M292 30V312M30 188H606" className="sp-haulc" />
          <g className="sp-gate" transform="translate(332 322)"><rect x="-16" y="-3" width="32" height="6" rx="1" /><text y="-9" textAnchor="middle">Gate</text></g>
        </g>
        {ZONES.map((z) => {
          const sh = SHAPES[z.id]
          if (!sh) return null
          const s = byId[z.id]
          const st = s?.status
          const mood = st || 'clear'
          const alert = st && st !== 'info'
          const selected = selectedZone === z.id
          const [tx, ty] = sh.tag
          const [dx, dy] = sh.dot
          const w = 14 + z.label.length * 7
          return (
            <g key={z.id} className={'sp-zone status-' + mood + (selected ? ' selected' : '')} tabIndex={0} role="button"
               aria-label={z.label + ': ' + (st ? SEVERITY[st].label + ' alert' : 'clear') + '. Click to ' + (selected ? 'show all areas' : 'see its incidents')}
               onClick={() => pick(z, selected)}
               onKeyDown={(ev) => (ev.key === 'Enter' || ev.key === ' ') && pick(z, selected)}>
              <polygon points={sh.pts} className="sp-poly" />
              <g className="sp-tag" transform={`translate(${tx} ${ty})`}>
                <rect width={Math.max(w, 112)} height="40" rx="6" className="sp-tag-bg" />
                <text x="10" y="16" className="sp-tag-name">{z.label}</text>
                <circle cx="14" cy="29" r="4" className="sp-tag-dot" />
                <text x="24" y="33" className="sp-tag-state">{LABEL[mood]}</text>
              </g>
              <g transform={`translate(${dx} ${dy})`} className="sp-marker">
                {alert && <circle r="11" className="sp-ring" />}
                <circle r="10" className="sp-mk" />
                {st && <text y="4" textAnchor="middle" className="sp-mk-n">{s.recent || ''}</text>}
              </g>
            </g>
          )
        })}
        <g className="sp-key" transform="translate(12 339)" aria-hidden="true">
          <rect width="268" height="26" rx="6" className="sp-key-bg" />
          {KEY.map(([k, t], i) => <g key={k} transform={`translate(${10 + i * 66} 13)`} className={'status-' + k}><circle r="4.5" className="sp-key-dot" /><text x="9" y="4">{t}</text></g>)}
        </g>
        <text x="630" y="357" textAnchor="end" className="sp-attr">Schematic plan, not to scale</text>
      </svg>
      {sel && (
        <div className="gm-card" role="status">
          <div><b>{sel.label}</b><span className={'gm-badge st-' + (sel.status || 'clear')}>{LABEL[sel.status || 'clear']}</span></div>
          <p>{sel.total ? sel.total + (sel.total === 1 ? ' incident' : ' incidents') + ' recorded, ' + sel.recent + ' in the last 15 minutes.' : 'No incidents recorded here.'}</p>
          <button className="link" onClick={() => onSelectZone?.('all')}>Clear selection</button>
        </div>
      )}
      {other.length > 0 && (
        <p className="other-zones">Areas reporting that are not drawn on the map: {other.map((z) => z.label + ' (' + z.total + ')').join(', ')}</p>
      )}
    </div>
  )
}
