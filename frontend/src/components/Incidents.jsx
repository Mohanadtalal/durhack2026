import React, { useEffect, useState } from 'react'
import { X, ImageOff, ExternalLink, Image as ImageIcon } from 'lucide-react'
import { SeverityTag, SourceTag, Empty } from './Common'
import { SEVERITY_ORDER, SEVERITY, WINDOWS, friendly, plainTitle, timeAgo } from '../config'


function EvidenceImage({ incident, full = false }) {
  const [failed, setFailed] = useState(false)
  useEffect(() => setFailed(false), [incident?.snapshot])
  const valid = Boolean(incident?.snapshot && !failed)
  const label = failed ? 'Image unavailable' : (incident?.snapshot ? 'Loading evidence…' : 'No snapshot')
  return (
    <div className={full ? 'snapshot-full' : 'snapshot-thumb'}>
      {valid
        ? <img src={incident.snapshot}
            alt={'Captured evidence for ' + friendly(incident.hazard_type)}
            loading={full ? 'eager' : 'lazy'}
            onError={() => setFailed(true)} />
        : <span className="snapshot-placeholder"><ImageOff size={full ? 26 : 18} />
            <small>{label}</small></span>}
    </div>
  )
}

export function SnapshotGallery({ incidents, onOpen }) {
  const available = incidents.filter((incident) => incident.snapshot).slice(0, 6)
  if (!available.length) return <Empty>No saved alert images yet. New camera detections will have snapshots once the evidence API is running.</Empty>
  return (
    <div className="snapshot-gallery">
      {available.map((incident) => (
        <button className="snapshot-gallery-card" key={incident.event_id}
            onClick={() => onOpen(incident)}>
          <EvidenceImage incident={incident} />
          <span className="snapshot-gallery-text">
            <strong>{plainTitle(incident)}</strong>
            <small>{new Date(incident.timestamp).toLocaleString()}</small>
          </span>
        </button>
      ))}
    </div>
  )
}

export function Filters({ filters, setFilters, events, shown }) {
  const hazards = [...new Set(events.map((e) => e.hazard_type))]
  const zones = [...new Set(events.map((e) => e.zone_id))]
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
            <div className="incident-content">
              <EvidenceImage incident={e} />
              <div className="incident-copy">
                <div className="incident-top">
                  <b>{plainTitle(e)}</b>
                  <SeverityTag severity={e.severity} />
                </div>
                <div className="incident-meta">
                  <span className="where">{friendly(e.zone_id)}</span>
                  <span title={new Date(e.timestamp).toLocaleString()}>{timeAgo(e.ts, now)}</span>
                  <SourceTag incident={e} />
                </div>
              </div>
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
        <div className="snapshot-detail-head">
          <h3><ImageIcon size={17} /> Captured evidence</h3>
          {incident.snapshot && <a className="snapshot-open" href={incident.snapshot}
            target="_blank" rel="noopener noreferrer">Open full image <ExternalLink size={14} /></a>}
        </div>
        <div className="evidence"><EvidenceImage incident={incident} full /></div>
        {!incident.snapshot && <p className="snapshot-help">
          {md.snapshot_status === 'capture_failed' ? 'The camera could not save this frame.'
            : md.snapshot_status === 'capture_unavailable' ? 'No frame was available when this alert occurred.'
            : 'This older incident has no attached snapshot.'}
        </p>}
        <p className="snapshot-annotation">Evidence is a captured camera frame from this incident, not a live feed.</p>
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
