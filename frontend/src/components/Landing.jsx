import React, { useEffect, useRef, useState } from 'react'
import { Walkthrough } from './Walkthrough'

// Sequence mirrors what edge/camera.py, the backend and this dashboard actually do.
const SEQUENCE = [
  ['Frame in', 'The camera node reads a frame and looks for people.'],
  ['Zone check', 'A rule asks one question: is a person inside the restricted area, and for how long?'],
  ['Local alarm', 'The node raises its own warning immediately. It does not wait for the network.'],
  ['Report', 'The incident is posted to the API and stored in MongoDB, or held in a queue if the link is down.'],
  ['On screen', 'It appears on the dashboard within a couple of seconds, tagged with its zone and severity.'],
  ['Review', 'On request, Gemini reads the stored history and points out where incidents keep repeating.'],
]
const COLORS = ['#8db3ff', '#c0a8ff', '#ff9a9e', '#62dccb', '#86e3a8', '#ffd36b']
const WORKING = [
  'Person-in-zone and dwell-time detection',
  'Local alarm independent of the backend',
  'Incident API with storage in MongoDB',
  'Live dashboard, filters, site plan, history',
  'Gemini summary of stored incidents',
]
const NEXT = [
  'Verified run on the Arduino UNO Q',
  'Hard-hat and machinery detection',
  'Gemini reading camera frames, not just records',
  'Evidence images attached to incidents',
  'Marking incidents resolved',
]

export function Landing({ onOpen }) {
  const root = useRef(null)
  const track = useRef(null)
  const [active, setActive] = useState(0)

  useEffect(() => {
    const el = root.current
    if (!el) return undefined
    const reduce = window.matchMedia?.('(prefers-reduced-motion: reduce)').matches
    const io = new IntersectionObserver((entries) => entries.forEach((e) => {
      if (e.isIntersecting) { e.target.classList.add('in'); io.unobserve(e.target) }
    }), { threshold: 0.2 })
    el.querySelectorAll('[data-reveal]').forEach((n) => (reduce ? n.classList.add('in') : io.observe(n)))
    if (reduce) return () => io.disconnect()

    let raf = 0
    const update = () => {
      raf = 0
      const y = window.scrollY
      const hero = el.querySelector('.l-top')
      const hh = hero ? hero.offsetHeight : 700
      el.style.setProperty('--hp', Math.min(1, y / (hh * 0.85)).toFixed(3))
      const doc = document.documentElement
      doc.style.setProperty('--sp', (y / Math.max(1, doc.scrollHeight - window.innerHeight)).toFixed(4))
      const t = track.current
      if (t && window.innerWidth > 900) {
        const r = t.getBoundingClientRect()
        const total = Math.max(1, r.height - window.innerHeight)
        const p = Math.max(0, Math.min(1, -r.top / total))
        setActive(Math.min(SEQUENCE.length - 1, Math.floor(p * SEQUENCE.length)))
      }
    }
    const onScroll = () => { if (!raf) raf = requestAnimationFrame(update) }
    update()
    window.addEventListener('scroll', onScroll, { passive: true })
    window.addEventListener('resize', onScroll)
    return () => {
      io.disconnect()
      window.removeEventListener('scroll', onScroll)
      window.removeEventListener('resize', onScroll)
      document.documentElement.style.removeProperty('--sp')
    }
  }, [])

  return (
    <div className="landing" ref={root}>
      <div className="l-progress" aria-hidden="true" />
      <div className="l-top">
        <section className="l-hero">
          <div className="l-copy">
            <p className="l-kicker">DurHack 2026 · RS Group challenge</p>
            <h1>
              <span className="ln" style={{ '--i': 0 }}><span>Every near miss,</span></span>
              <span className="ln" style={{ '--i': 1 }}><span>caught on site,</span></span>
              <span className="ln" style={{ '--i': 2 }}><span>then kept on record.</span></span>
            </h1>
            <p className="l-sub">SiteGuardian watches a work zone through a camera node, sounds an alarm on the spot, and logs each incident so a site team can see where risk keeps coming back.</p>
            <div className="l-cta">
              <button className="primary big" onClick={() => onOpen('overview')}>Open the dashboard</button>
              <button className="textlink" onClick={() => onOpen('camera')}>Camera view</button>
            </div>
          </div>
          <div className="l-demo"><Walkthrough /></div>
        </section>
      </div>

      <section className="l-band l-seq-section">
        <div className="seq-track" ref={track}>
          <div className="seq-stick">
            <div className="l-wrap l-split seq-grid">
              <div className="seq-left">
                <h2>What happens when someone steps into a zone</h2>
                <p className="l-lead">Six steps, in the order the code runs them.</p>
                <div className="seq-big" key={active} style={{ '--c': COLORS[active] }}>
                  <span className="seq-n">{active + 1} of {SEQUENCE.length}</span>
                  <b>{SEQUENCE[active][0]}</b>
                </div>
              </div>
              <ol className="l-seq seq-rows">
                {SEQUENCE.map(([name, text], i) => (
                  <li key={name} className={i === active ? 'on' : i < active ? 'past' : ''} style={{ '--c': COLORS[i] }}>
                    <b>{name}</b><span>{text}</span>
                  </li>
                ))}
              </ol>
            </div>
          </div>
        </div>
      </section>

      <div className="l-statusband">
        <section className="l-wrap l-split l-status">
          <div data-reveal className="rv">
            <h2>Where the prototype stands</h2>
            <p className="l-lead">Nothing here is claimed that the code does not do. Hardware and camera runs are still to be verified by the team.</p>
          </div>
          <div className="l-cols" data-reveal>
            <div className="wipe"><h3>Built</h3><ul>{WORKING.map((t, i) => <li key={t} style={{ '--k': i }}>{t}</li>)}</ul></div>
            <div className="wipe" style={{ '--d': '.15s' }}><h3>Still to do</h3><ul className="todo">{NEXT.map((t, i) => <li key={t} style={{ '--k': i }}>{t}</li>)}</ul></div>
          </div>
        </section>
      </div>
    </div>
  )
}
