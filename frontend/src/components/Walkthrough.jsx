import React, { useEffect, useState } from 'react'

// Illustrated loop of the real pipeline (edge zone rule -> local alarm -> API -> dashboard).
// Nothing here is live data; the panel says so.
const STEPS = [
  { name: 'Frame in', log: 'One person detected in frame' },
  { name: 'Zone check', log: 'Person is outside the restricted zone' },
  { name: 'Local alarm', log: 'Person inside the zone. Alarm raised on the node' },
  { name: 'Report', log: 'Incident sent to the API' },
  { name: 'On screen', log: 'Incident visible on the dashboard' },
]
const PERSON_X = [70, 215, 332, 332, 332, 332]
const STEP_MS = 1900

export function Walkthrough() {
  const reduce = typeof window !== 'undefined' && window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
  const [step, setStep] = useState(reduce ? 4 : 0)
  useEffect(() => {
    if (reduce) return
    const t = setInterval(() => setStep((s) => (s + 1) % 7), STEP_MS)
    return () => clearInterval(t)
  }, [reduce])
  const s = Math.min(step, 4)
  const alarm = s >= 2
  const x = PERSON_X[Math.min(step, 5)]
  const resetting = step >= 5

  return (
    <div className={'wt' + (alarm ? ' wt-alarm' : '')} role="img" aria-label="Illustration: a person enters a restricted zone, the node raises an alarm, and the incident appears on the dashboard">
      <div className="wt-rail">
        {STEPS.map((st, i) => (
          <span key={st.name} className={i === s ? 'on' : i < s ? 'done' : ''}>{st.name}</span>
        ))}
      </div>
      <div className="wt-body">
        <svg viewBox="0 0 520 300" className="wt-scene" aria-hidden="true">
          <defs>
            <pattern id="wtg" width="20" height="20" patternUnits="userSpaceOnUse"><path d="M20 0H0V20" fill="none" stroke="#12325b14" /></pattern>
          </defs>
          <rect width="520" height="300" fill="#f5f7fb" />
          <rect width="520" height="300" fill="url(#wtg)" />
          <polygon points="52,44 505,14 505,292" className="wt-fov" />
          <line x1="40" y1="205" x2="300" y2="205" className="wt-path" />
          <rect x="290" y="105" width="190" height="155" className="wt-zone" />
          <text x="302" y="126" className="wt-zone-label">Cutting station A, restricted</text>
          <rect x="365" y="160" width="84" height="64" className="wt-machine" />
          <text x="407" y="197" textAnchor="middle" className="wt-machine-label">Saw</text>
          <g transform="translate(34 38)">
            <rect width="30" height="20" rx="3" className="wt-cam" /><circle cx="15" cy="10" r="5" className="wt-cam-lens" />
          </g>
          <text x="34" y="78" className="wt-small">Camera node</text>
          {alarm && (
            <g>
              <circle cx="49" cy="48" r="10" className="wt-ring" /><circle cx="49" cy="48" r="10" className="wt-ring r2" />
              <rect x="76" y="34" width="104" height="24" rx="12" className="wt-badge" />
              <text x="128" y="50" textAnchor="middle" className="wt-badge-text">Alarm on node</text>
            </g>
          )}
          <g className={'wt-person' + (resetting ? ' reset' : '')} style={{ transform: `translate(${x}px, 205px)` }}>
            <rect x="-15" y="-48" width="30" height="56" className="wt-box" />
            <text x="-15" y="-54" className="wt-box-label">person</text>
            <circle cx="0" cy="-26" r="7" className="wt-head" /><rect x="-6" y="-17" width="12" height="22" rx="5" className="wt-body-fig" />
          </g>
        </svg>
        <div className="wt-side">
          <ol className="wt-log">
            {STEPS.slice(0, 4).map((st, i) => (
              <li key={st.name} className={'c' + (i + 1) + (i <= s ? ' show' : '')}><time>+{(i * STEP_MS / 1000).toFixed(1)} s</time><span>{st.log}</span></li>
            ))}
          </ol>
          <div className={'wt-card' + (s >= 4 ? ' show' : '')}>
            <div><b>Zone Entry</b><span className="wt-tag">Warning</span></div>
            <p>Cutting Station A</p>
          </div>
        </div>
      </div>
      <p className="wt-note">Illustrated walkthrough of the flow. Not live data.</p>
    </div>
  )
}
