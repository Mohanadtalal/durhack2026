import React from 'react'
import { SEVERITY_ORDER, SEVERITY, friendly } from '../config'
import { Empty } from './Common'

function count(list, key) {
  const m = {}
  list.forEach((e) => { m[e[key]] = (m[e[key]] || 0) + 1 })
  return m
}

export function Bars({ data, order, labelOf, colorClass }) {
  const entries = (order || Object.keys(data)).map((k) => [k, data[k] || 0])
  const max = Math.max(1, ...entries.map(([, v]) => v))
  return (
    <div className="bars">
      {entries.map(([k, v]) => (
        <div className="bar-row" key={k}>
          <span className="bar-label">{labelOf ? labelOf(k) : friendly(k)}</span>
          <div className="bar-track"><div className={'bar-fill ' + (colorClass ? colorClass(k) : '')} style={{ width: (100 * v) / max + '%' }} /></div>
          <b>{v}</b>
        </div>
      ))}
    </div>
  )
}

export function SeverityBreakdown({ events }) {
  if (!events.length) return <Empty>No incidents match the current filters.</Empty>
  return <Bars data={count(events, 'severity')} order={SEVERITY_ORDER} labelOf={(k) => SEVERITY[k].label} colorClass={(k) => 'fill-' + k} />
}

export function HazardBreakdown({ events }) {
  if (!events.length) return <Empty>Hazard counts appear once the detector logs events.</Empty>
  const data = count(events, 'hazard_type')
  const order = Object.keys(data).sort((a, b) => data[b] - data[a])
  return <Bars data={data} order={order} />
}

export function ZoneBreakdown({ events }) {
  if (!events.length) return <Empty>No zone data yet.</Empty>
  const data = count(events, 'zone_id')
  const order = Object.keys(data).sort((a, b) => data[b] - data[a])
  return <Bars data={data} order={order} />
}

// Incidents over time: 12 equal buckets between the first event and now.
export function Trend({ events, now }) {
  if (events.length < 2) return <Empty>A trend appears once there are at least two incidents.</Empty>
  const start = Math.min(...events.map((e) => e.ts))
  const span = Math.max(1, now - start)
  const buckets = Array.from({ length: 12 }, () => ({ n: 0, worst: 0 }))
  events.forEach((e) => {
    const i = Math.min(11, Math.floor(((e.ts - start) / span) * 12))
    buckets[i].n += 1
    buckets[i].worst = Math.max(buckets[i].worst, SEVERITY[e.severity]?.rank ?? 0)
  })
  const max = Math.max(1, ...buckets.map((b) => b.n))
  const cls = ['info', 'warning', 'high', 'critical']
  const fmt = (t) => new Date(t).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
  return (
    <div>
      <svg viewBox="0 0 360 120" className="trend" role="img" aria-label="Incidents over time">
        {buckets.map((b, i) => {
          const h = (b.n / max) * 96
          return <rect key={i} x={i * 30 + 3} y={110 - h} width="24" height={Math.max(h, b.n ? 3 : 1)} className={'trend-bar fill-' + cls[b.worst]} rx="2"><title>{b.n} incidents</title></rect>
        })}
        <line x1="0" y1="110.5" x2="360" y2="110.5" className="trend-axis" />
      </svg>
      <div className="trend-axis-labels"><span>{fmt(start)}</span><span>{fmt(now)}</span></div>
    </div>
  )
}
