import React, { useCallback, useMemo, useState } from 'react'
import { BrainCircuit, HelpCircle, Camera, CheckCircle2, History, LayoutDashboard, Map as MapIcon, Menu, RefreshCcw, ShieldCheck, WifiOff, X } from 'lucide-react'
import { postEvent, runInsights } from './api'
import { useIncidents } from './hooks/useIncidents'
import { useCameraStatus } from './hooks/useCameraStatus'
import { ACTIVE_WINDOW_MS, WINDOWS, timeAgo } from './config'
import { CountUp, Panel } from './components/Common'
import { StatusHero } from './components/StatusHero'
import { SiteMap, zoneSummaries } from './components/SiteMap'
import { HazardBreakdown, SeverityBreakdown, Trend, ZoneBreakdown } from './components/Charts'
import { Filters, IncidentDetail, IncidentList, Timeline } from './components/Incidents'
import { InsightPanel } from './components/Insights'
import { Toasts } from './components/Toasts'
import { CameraFeed } from './components/CameraFeed'
import { Landing } from './components/Landing'
import { Guide } from './components/Guide'

const VIEWS = [
  { id: 'home', label: 'Home', icon: ShieldCheck },
  { id: 'overview', label: 'Overview', icon: LayoutDashboard, blurb: 'The quick picture: is anything wrong on site right now?' },
  { id: 'camera', label: 'Camera', icon: Camera, blurb: 'The camera view, with the most recent incidents beside it.' },
  { id: 'zones', label: 'Camera zones', icon: MapIcon, blurb: 'Real marked regions from the connected camera; incidents without known polygons are listed separately.' },
  { id: 'history', label: 'History', icon: History, blurb: 'Every recorded incident. Use the menus to narrow the list.' },
  { id: 'insights', label: 'AI review', icon: BrainCircuit, blurb: 'Ask an AI to spot patterns in past incidents. It only suggests, people decide.' },
]
const DEFAULT_FILTERS = { severity: 'all', hazard: 'all', zone: 'all', window: 'all' }

export default function App() {
  const [view, setView] = useState('home')
  const [menuOpen, setMenuOpen] = useState(false)
  const [filters, setFilters] = useState(DEFAULT_FILTERS)
  const [selected, setSelected] = useState(null)
  const [toasts, setToasts] = useState([])
  const [insight, setInsight] = useState(null)
  const [insightAt, setInsightAt] = useState(null)
  const [insightLoading, setInsightLoading] = useState(false)
  const [insightError, setInsightError] = useState('')
  const [simError, setSimError] = useState('')
  const [guideOpen, setGuideOpen] = useState(false)
  const [tipGone, setTipGone] = useState(() => { try { return localStorage.getItem('sg-tip') === '1' } catch { return false } })
  const closeGuide = useCallback(() => setGuideOpen(false), [])
  const hideTip = () => { setTipGone(true); try { localStorage.setItem('sg-tip', '1') } catch { /* ignore */ } }

  const dismiss = useCallback((id) => setToasts((t) => t.filter((x) => x.id !== id)), [])
  const onNew = useCallback((fresh) => {
    const important = fresh.filter((e) => e.severity !== 'info').slice(0, 3)
    important.forEach((e) => setTimeout(() => dismiss(e.event_id), 7000))
    setToasts((t) => [...important.map((e) => ({ ...e, id: e.event_id })), ...t].slice(0, 4))
  }, [dismiss])

  const { events, health, error, lastUpdated, now, refresh } = useIncidents(onNew)
  const { cameraStatus, cameraError } = useCameraStatus()

  const filtered = useMemo(() => {
    const w = WINDOWS.find((x) => x.id === filters.window)?.ms ?? Infinity
    return events.filter((e) =>
      (filters.severity === 'all' || e.severity === filters.severity) &&
      (filters.hazard === 'all' || e.hazard_type === filters.hazard) &&
      (filters.zone === 'all' || e.zone_id === filters.zone) &&
      now - e.ts <= w)
  }, [events, filters, now])

  const high = filtered.filter((e) => e.severity === 'high' || e.severity === 'critical').length
  const activeZones = zoneSummaries(events, now, cameraStatus?.zones || [])
    .filter((z) => z.recent > 0).length
  const latest = events[0]

  async function simulate(kind) {
    setSimError('')
    const prolonged = kind === 'prolonged_exposure'
    try {
      await postEvent({
        source_id: 'dashboard-simulator',
        zone_id: prolonged ? 'cutting-station-a' : 'loading-zone-b',
        hazard_type: kind,
        severity: prolonged ? 'high' : 'warning',
        description: 'Simulated ' + kind.replaceAll('_', ' ') + ' from the dashboard button',
        metadata: { simulated: true },
      })
      await refresh()
    } catch (exc) { setSimError('Simulation failed: ' + exc.message) }
  }

  async function analyse() {
    setInsightLoading(true); setInsightError('')
    try { setInsight(await runInsights()); setInsightAt(Date.now()) }
    catch (exc) { setInsightError(exc.message) }
    finally { setInsightLoading(false) }
  }

  const go = (id) => { setView(id); setMenuOpen(false) }
  const selectZone = (zone) => { setFilters({ ...filters, zone }); }
  const insightPanel = <InsightPanel insight={insight} loading={insightLoading} error={insightError} canRun={events.length > 0} onRun={analyse} generatedAt={insightAt} />

  return (
    <div className="layout">
      <a className="skip" href="#content">Skip to content</a>
      <header className="site-nav">
        <div className="site-nav-in">
          <button className="logo-btn" onClick={() => go('home')} aria-label="SiteGuardian home"><span className="logo-mark"><ShieldCheck size={17} /></span><span className="logo-text">SiteGuardian</span></button>
          <nav aria-label="Main">
            {VIEWS.map(({ id, label }) => (
              <button key={id} className={'nav-link' + (view === id ? ' active' : '')} onClick={() => go(id)} aria-current={view === id ? 'page' : undefined}>{label}</button>
            ))}
          </nav>
          <button className="help-btn" onClick={() => setGuideOpen(true)}><HelpCircle size={16} /> Help</button>
          <div className={'health ' + (health ? 'ok' : 'down')} role="status">{health ? <><CheckCircle2 size={15} /> Online</> : <><WifiOff size={15} /> Offline</>}</div>
        </div>
      </header>

      <main key={view} id="content" className={view === 'home' ? 'is-home' : ''}>
        {view !== 'home' && <div className="page-head">
          <div>
            <h1>{VIEWS.find((v) => v.id === view).label}</h1>
            <p className="page-blurb">{VIEWS.find((v) => v.id === view).blurb}</p>
            <p className="page-upd">{lastUpdated ? 'Updated ' + timeAgo(lastUpdated, now) : 'Connecting to the server…'}</p>
          </div>
          <div className={'health ' + (health ? 'ok' : 'down')} role="status">
            {health ? <><CheckCircle2 size={16} /> Connected</> : <><WifiOff size={16} /> Can't reach the server</>}
          </div>
        </div>}

        {view !== 'home' && error && <div className="error" role="alert">Can't reach the server right now, so this page may be out of date. Check that the backend is running. ({error})</div>}
        {view !== 'home' && health?.storage_mode === 'memory' && <div className="notice">Practice mode: incidents are only kept temporarily and disappear when the server restarts.</div>}

        {view !== 'home' && !tipGone && <div className="tip"><span><b>New here?</b> A two-minute guide explains every colour and word on this site.</span><button className="primary" onClick={() => { setGuideOpen(true); hideTip() }}>Open the guide</button><button className="link" onClick={hideTip}>No thanks</button></div>}

        {view === 'home' && <Landing events={events} now={now} onOpen={go} />}
        {view === 'overview' && <StatusHero events={events} now={now} />}

        {view === 'overview' && (<>
          <div className="grid two">
            <Panel tone="blue" title="Camera zones" note="Actual saved camera regions when connected; unmapped incidents remain listed.">
              <SiteMap events={events} now={now} selectedZone={filters.zone} onSelectZone={selectZone} cameraStatus={cameraStatus} />
            </Panel>
            <Panel tone="violet" title="Latest incidents" note="Newest first. Click one for the full story." action={<button className="icon-btn" onClick={refresh} aria-label="Refresh now"><RefreshCcw size={17} /></button>}>
              <div className="scroll tall"><IncidentList incidents={filtered.slice(0, 6)} now={now} onOpen={setSelected} /></div>
            </Panel>
          </div>
          <div className="grid cam">
            <Panel tone="teal" title="Camera" note="What the camera on site sees"><CameraFeed latest={events[0]} now={now} cameraStatus={cameraStatus} cameraError={cameraError} /></Panel>
            <Panel tone="pink" title="AI pattern review" note="Gemini looks for problems that keep repeating"><div className="scroll tall">{insightPanel}</div></Panel>
          </div>
          <details className="sim">
            <summary>Try it: make a practice alert</summary>
            <p className="muted">Handy if nothing has been reported yet. These make a practice incident, clearly labelled Simulated, so you can see how alerts look. They are not real detections.</p>
            <div className="actions">
              <button className="primary" onClick={() => simulate('zone_entry')}>Practice: someone enters a zone</button>
              <button className="secondary" onClick={() => simulate('prolonged_exposure')}>Practice: someone stays too long</button>
            </div>
            {simError && <div className="error" role="alert">{simError}</div>}
            <p className="muted">Or run <code>python -m edge.demo</code> to send events the way the edge agent does.</p>
          </details>
        </>)}

        {view === 'camera' && (
          <div className="grid cam">
            <Panel title="Camera" note="What the camera on site sees"><CameraFeed latest={events[0]} now={now} cameraStatus={cameraStatus} cameraError={cameraError} /></Panel>
            <Panel title="Incidents from the camera" note="Newest first"><div className="scroll tall"><IncidentList incidents={events.slice(0, 20)} now={now} onOpen={setSelected} /></div></Panel>
          </div>
        )}

        {view === 'zones' && (
          <div className="grid two">
            <Panel title="Camera zones" note="Select an actual camera region or an incident-only area.">
              <SiteMap events={events} now={now} selectedZone={filters.zone} onSelectZone={selectZone} cameraStatus={cameraStatus} />
            </Panel>
            <Panel title={filters.zone === 'all' ? 'Incidents by zone' : 'Incidents in selected zone'}>
              {filters.zone === 'all'
                ? <ZoneBreakdown events={events} />
                : <><button className="link" onClick={() => selectZone('all')}>Show all zones</button><div className="scroll"><IncidentList incidents={events.filter((e) => e.zone_id === filters.zone)} now={now} onOpen={setSelected} emptyText="No incidents recorded in this zone." /></div></>}
            </Panel>
          </div>
        )}

        {view === 'history' && (<>
          <Filters filters={filters} setFilters={setFilters} events={events} shown={filtered.length} />
          <div className="grid two">
            <Panel title="Incidents"><div className="scroll tall"><IncidentList incidents={filtered} now={now} onOpen={setSelected} emptyText="No incidents match these filters." /></div></Panel>
            <div className="stack">
              <Panel title="Timeline" note="Most recent 15 for the current filters"><Timeline incidents={filtered} now={now} onOpen={setSelected} /></Panel>
              <Panel title="Trouble spots" note="Areas with the most incidents come first"><ZoneBreakdown events={filtered} /></Panel>
              <Panel title="How serious"><SeverityBreakdown events={filtered} /></Panel>
              <Panel title="When it happens"><Trend events={filtered} now={now} /></Panel>
            </div>
          </div>
        </>)}

        {view === 'insights' && (
          <Panel title="AI safety review" note="Gemini reads saved incidents only. It never sets off an alarm.">{insightPanel}</Panel>
        )}

        <footer>SiteGuardian is a hackathon prototype. Test cameras and alarms before any real use.</footer>
      </main>

      <Guide open={guideOpen} onClose={closeGuide} onGo={go} />
      <Toasts toasts={toasts} dismiss={dismiss} />
      <IncidentDetail incident={selected} onClose={() => setSelected(null)} />
    </div>
  )
}
