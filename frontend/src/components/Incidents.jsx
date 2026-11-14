import React, { useEffect } from 'react'
import { X, ImageOff } from 'lucide-react'
import { SeverityTag, SourceTag, Empty } from './Common'
import { SEVERITY_ORDER, SEVERITY, WINDOWS, ZONES, friendly, plainTitle, timeAgo } from '../config'

export function Filters({ filters, setFilters, events, shown }) {
  const hazards = [...new Set(events.map((e) => e.hazard_type))]
  const zones = [...new Set([...ZONES.map((z) => z.id), ...events.map((e) => e.zone_id)])]
  const set = (k) => (ev) => setFilters({ ...filters, [k]: ev.target.value })
  const active = Object.entries(filters).some(([k, v]) => v !== 'all')
  return (
    <div className="filters">
      <label>How serious
        <select value={filters.severity} onChange={set('severity')}>
          <option value="all">Any level</option>
          {SEVERITY_ORDER.map((s) => <option key={s} value={s}>{SEVERITY[s].label}</option>)}
        </select>
      </label>
      <label>What happened
        <select value={filters.hazard} onChange={set('hazard')}>
          <option value="all">Anything</option>
          {hazards.map((h) => <option key={h} value={h}>{plainTitle({ hazard_type: h })}</option>)}
        </select>
      </label>
      <label>Area
        <select value={filters.zone} onChange={set('zone')}>
          <option value="all">All areas</option>
          {zones.map((z) => <option key={z} value={z}>{friendly(z)}</option>)}
        </select>
      </label>
      <label>When
        <select value={filters.window} onChange={set('window')}>
          {WINDOWS.map((w) => <option key={w.id} value={w.id}>{w.label}</option>)}
        </select>
      </label>
      <div className="filter-count">
        Showing {shown} of {events.length}
        {active && <button className="link" onClick={() => setFilters({ severity: 'all', hazard: 'all', zone: 'all', window: 'all' })}>Clear filters</button>}
      </div>
    </div>
  )
}

export function IncidentList({ incidents, now, onOpen, emptyText }) {
  if (!incidents.length) return <Empty>{emptyText || 'Nothing here yet, which is fine. Incidents appear as soon as the camera reports one. To see how they look, use "Try it" on the Overview page.'}</Empty>
  return (
    <ul className="incidents">
      {incidents.map((e) => (
        <li key={e.event_id}>
          <button className={'incident sev-edge-' + e.severity} onClick={() => onOpen(e)}>
            <div className="incident-top">
              <b>{plainTitle(e)}</b>
              <SeverityTag severity={e.severity} />
            </div>
            <div className="incident-meta">
              <span className="where">{friendly(e.zone_id)}</span>
              <span title={new Date(e.timestamp).toLocaleString()}>{timeAgo(e.ts, now)}</span>
              <SourceTag incident={e} />
            </div>
          </button>
        </li>
      ))}
    </ul>
  )
}

export function Timeline({ incidents, now, onOpen }) {
  if (!incidents.length) return <Empty>Nothing to show on the timeline for these filters.</Empty>
  return (
    <ol className="timeline">
      {incidents.slice(0, 15).map((e) => (
        <li key={e.event_id} className={'tl-' + e.severity}>
          <button onClick={() => onOpen(e)}>
            <time>{new Date(e.timestamp).toLocaleTimeString()}</time>
            <span>{friendly(e.hazard_type)} in {friendly(e.zone_id)}</span>
            <em>{timeAgo(e.ts, now)}</em>
          </button>
        </li>
      ))}
    </ol>
  )
}

export function IncidentDetail({ incident, onClose }) {
  useEffect(() => {
    const onKey = (ev) => ev.key === 'Escape' && onClose()
    window.addEventListener('keydown', onKey)
    return () => window.removeEventListener('keydown', onKey)
  }, [onClose])
  if (!incident) return null
  const md = incident.metadata || {}
  return (
    <div className="drawer-wrap" onClick={onClose}>
      <aside className="drawer" role="dialog" aria-modal="true" aria-label="Incident detail" onClick={(e) => e.stopPropagation()}>
        <div className="drawer-head">
          <div><h2>{friendly(incident.hazard_type)}</h2><p>{friendly(incident.zone_id)}</p></div>
          <button className="icon-btn" onClick={onClose} aria-label="Close detail"><X size={18} /></button>
        </div>
        <div className="drawer-tags"><SeverityTag severity={incident.severity} /><SourceTag incident={incident} /></div>
        <p className="drawer-desc">{incident.description}</p>
        <div className="evidence">
          {incident.snapshot
            ? <img src={incident.snapshot} alt={'Evidence for ' + friendly(incident.hazard_type)} />
            : <div className="evidence-empty"><ImageOff size={22} /><span>No image evidence attached to this incident.</span><small>Evidence appears here when the edge agent includes <code>metadata.snapshot_url</code>.</small></div>}
        </div>
        <dl className="facts">
          <dt>Time</dt><dd>{new Date(incident.timestamp).toLocaleString()}</dd>
          <dt>Source</dt><dd>{incident.source_id}</dd>
          <dt>Event ID</dt><dd className="mono">{incident.event_id}</dd>
          {incident.confidence !== null && (<><dt>Confidence</dt><dd>{Math.round(incident.confidence * 100)}%</dd></>)}
        </dl>
        {Object.keys(md).length > 0 && <details><summary>Raw metadata</summary><pre>{JSON.stringify(md, null, 2)}</pre></details>}
        <p className="drawer-note">Alerts support, and do not replace, qualified safety staff.</p>
      </aside>
    </div>
  )
}
