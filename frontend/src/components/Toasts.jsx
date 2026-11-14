import React from 'react'
import { AlertTriangle, X } from 'lucide-react'
import { SEVERITY, friendly } from '../config'

export function Toasts({ toasts, dismiss }) {
  return (
    <div className="toasts" role="status" aria-live="polite">
      {toasts.map((t) => (
        <div key={t.id} className={'toast toast-' + t.severity}>
          <AlertTriangle size={18} />
          <div>
            <b>{SEVERITY[t.severity]?.label || t.severity}: {friendly(t.hazard_type)}</b>
            <span>{friendly(t.zone_id)}{t.simulated ? ' (simulated)' : ''}</span>
          </div>
          <button className="icon-btn" onClick={() => dismiss(t.id)} aria-label="Dismiss alert"><X size={16} /></button>
        </div>
      ))}
    </div>
  )
}
