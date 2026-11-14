import React, { useEffect, useRef } from 'react'
import { X } from 'lucide-react'

const STEPS = [
  ['Check the banner', 'On the Overview page the big banner says in words whether anything was reported in the last 15 minutes.'],
  ['Look at the site map', 'Each outlined shape is a work area. Its colour and label show the latest alert there, and the number on its dot is how many incidents in the last 15 minutes. Click a shape to see only that area.'],
  ['Open an incident', 'Click any item in the list to see what happened, where, when, and how sure the camera was.'],
  ['Ask for an AI review', 'On the AI review page, Gemini reads the stored history and points out places where problems repeat.'],
]
const COLOURS = [
  ['clear', 'Clear', 'Nothing reported here recently.'],
  ['warning', 'Warning', 'Someone entered a restricted area.'],
  ['high', 'High alert', 'Someone stayed in a restricted area too long.'],
  ['critical', 'Critical', 'Needs attention straight away.'],
]
const WORDS = [
  ['Incident', 'One event the system recorded, such as someone entering a restricted area.'],
  ['Zone', 'A named work area on the site, like "Cutting station A".'],
  ['Restricted area', 'A zone people should not stand in while work is happening.'],
  ['Simulated', 'A practice incident made by a button or demo. It is not a real detection and is always labelled.'],
  ['Edge report', 'An incident sent by the camera device on site.'],
  ['Gemini', 'An AI service that reads the saved incidents and suggests patterns. It never sets off an alarm.'],
]

export function Guide({ open, onClose, onGo }) {
  const ref = useRef(null)
  useEffect(() => {
    if (!open) return undefined
    const prev = document.activeElement
    ref.current?.focus()
    const key = (e) => e.key === 'Escape' && onClose()
    window.addEventListener('keydown', key)
    return () => { window.removeEventListener('keydown', key); prev?.focus?.() }
  }, [open, onClose])
  if (!open) return null
  return (
    <div className="guide-wrap" onClick={onClose}>
      <aside className="guide" role="dialog" aria-modal="true" aria-label="Beginner's guide" tabIndex={-1} ref={ref} onClick={(e) => e.stopPropagation()}>
        <div className="guide-head">
          <h2>New here? Start here</h2>
          <button className="icon-btn" onClick={onClose} aria-label="Close guide"><X size={18} /></button>
        </div>
        <p className="guide-lead">SiteGuardian watches a work area through a camera, sounds an alarm on site when someone enters a restricted zone, and keeps a record. This website is where you read that record. You cannot break anything by clicking around.</p>

        <h3>Four easy steps</h3>
        <ol className="guide-steps">{STEPS.map(([t, d]) => <li key={t}><b>{t}</b><span>{d}</span></li>)}</ol>

        <h3>What the colours mean</h3>
        <ul className="guide-colours">{COLOURS.map(([k, t, d]) => <li key={k}><i className={'lg lg-' + k} /><b>{t}</b><span>{d}</span></li>)}</ul>

        <h3>Words you will see</h3>
        <dl className="guide-words">{WORDS.map(([t, d]) => <div key={t}><dt>{t}</dt><dd>{d}</dd></div>)}</dl>

        <h3>Good to know</h3>
        <ul className="guide-notes">
          <li>"Nothing reported" does not mean the site is safe. It only means nothing was recorded.</li>
          <li>Alerts support trained safety staff. They do not replace them.</li>
          <li>To see the site without real data, open the Overview page and use "Try it" to make a practice alert.</li>
        </ul>
        <div className="guide-cta">
          <button className="primary" onClick={() => { onGo('overview'); onClose() }}>Go to the overview</button>
          <button className="secondary" onClick={onClose}>Close</button>
        </div>
      </aside>
    </div>
  )
}
