import React, { useEffect, useState } from 'react'
import { SEVERITY } from '../config'

const SEV_HELP = { info: 'Minor: worth knowing, no action needed', warning: 'Warning: someone entered a restricted area', high: 'High: someone stayed in a restricted area too long', critical: 'Critical: needs attention straight away' }

export function SeverityTag({ severity }) {
  return <span className={'sev sev-' + severity} title={SEV_HELP[severity]}>{SEVERITY[severity]?.label || severity}</span>
}

// Non-simulated incidents are labelled "Edge report": the API does not say live vs recorded.
export function SourceTag({ incident }) {
  return incident.simulated
    ? <span className="src src-sim" title="Created by a simulator or demo button, not a real detection">Simulated</span>
    : <span className="src src-edge" title={'Reported by ' + incident.source_id}>Edge report</span>
}

export function Empty({ children }) {
  return <div className="empty">{children}</div>
}

export function Panel({ title, note, action, children, className = '', tone = '' }) {
  return (
    <section className={'panel ' + (tone ? 'tone-' + tone + ' ' : '') + className}>
      <div className="panel-head">
        <div><h2>{title}</h2>{note && <p>{note}</p>}</div>
        {action}
      </div>
      {children}
    </section>
  )
}

// Animates between numbers; jumps straight to the value if the user prefers reduced motion.
export function CountUp({ value }) {
  const [n, setN] = useState(value)
  useEffect(() => {
    if (window.matchMedia?.('(prefers-reduced-motion: reduce)').matches) { setN(value); return }
    let raf; const from = n; const t0 = performance.now()
    const step = (t) => { const k = Math.min(1, (t - t0) / 600); setN(Math.round(from + (value - from) * k)); if (k < 1) raf = requestAnimationFrame(step) }
    raf = requestAnimationFrame(step)
    return () => cancelAnimationFrame(raf)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [value])
  return n
}
