import React from 'react'
import { ShieldAlert, ShieldCheck, Info } from 'lucide-react'
import { ACTIVE_WINDOW_MS, friendly, topSeverity } from '../config'

const HEAD = {
  critical: 'Critical alert, act now',
  high: 'High alert, check the site',
  warning: 'Someone entered a restricted area',
  info: 'Minor activity noticed',
}

// Whole-site status from the last 15 minutes, in words. Colour carries the level.
export function StatusHero({ events, now }) {
  const recent = events.filter((e) => now - e.ts <= ACTIVE_WINDOW_MS)
  const status = topSeverity(recent)
  const zones = [...new Set(recent.filter((e) => e.severity === status).map((e) => friendly(e.zone_id)))]
  const Icon = status === 'critical' || status === 'high' ? ShieldAlert : status ? Info : ShieldCheck
  return (
    <section className={'hero hero-' + (status || 'clear')} aria-label="Site status">
      <div className="hero-icon" aria-hidden="true"><Icon size={44} /></div>
      <div className="hero-main">
        <h2 className="hero-title">{status ? HEAD[status] : 'Nothing reported in the last 15 minutes'}</h2>
        <p className="hero-note">{status
          ? 'Where: ' + zones.join(', ') + '. Open the incident below for details.'
          : 'That means nothing was reported, not that the site is safe. Alerts support qualified safety staff.'}</p>
      </div>
    </section>
  )
}
