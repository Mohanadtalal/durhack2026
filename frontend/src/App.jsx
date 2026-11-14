import React,{useEffect,useState} from 'react'
import {Activity,AlertTriangle,BrainCircuit,CheckCircle2,Database,HardHat,Radio,RefreshCcw,ShieldCheck,WifiOff} from 'lucide-react'

const API=import.meta.env.VITE_API_BASE||'http://127.0.0.1:8000'
async function api(path,opts){
  const r=await fetch(API+path,opts)
  if(!r.ok){
    const body=await r.json().catch(()=>({}))
    throw new Error(body.detail||'HTTP '+r.status)
  }
  return r.json()
}
function friendly(text){return String(text||'').replaceAll('_',' ').replace(/\b\w/g, c=>c.toUpperCase())}
export default function App(){
  const [events,setEvents]=useState([])
  const [stats,setStats]=useState({total:0,by_hazard:{},by_zone:{},by_severity:{}})
  const [health,setHealth]=useState(null)
  const [insight,setInsight]=useState(null)
  const [error,setError]=useState('')
  const [loading,setLoading]=useState(false)

  async function refresh(){
    try{
      const [e,s,h]=await Promise.all([api('/api/events?limit=40'),api('/api/stats'),api('/api/health')])
      setEvents(e);setStats(s);setHealth(h);setError('')
    }catch(exc){setHealth(null);setError('Backend: '+exc.message)}
  }
  useEffect(()=>{refresh();const t=setInterval(refresh,2500);return()=>clearInterval(t)},[])

  async function demo(kind){
    try{
      await api('/api/events',{method:'POST',headers:{'Content-Type':'application/json'},
        body:JSON.stringify({
          source_id:'dashboard-simulator',
          zone_id:kind==='prolonged_exposure'?'cutting-station-a':'loading-zone-b',
          hazard_type:kind,
          severity:kind==='prolonged_exposure'?'high':'warning',
          description:'Simulated hazard event from dashboard button',
          metadata:{simulated:true}
        })
      })
      await refresh()
    }catch(exc){setError('Simulation: '+exc.message)}
  }

  async function analyze(){
    setLoading(true);setError('')
    try{setInsight(await api('/api/insights',{method:'POST'}))}
    catch(exc){setError('Gemini: '+exc.message)}
    finally{setLoading(false)}
  }

  return <div className="layout">
    <aside className="sidebar">
      <div className="logo"><ShieldCheck size={29}/><div>SiteGuardian<span>AI</span><small>DURHACK 2026</small></div></div>
      <nav>
        <div className="nav active"><Activity size={18}/>Safety Overview</div>
        <div className="nav"><Radio size={18}/>Monitoring Zones</div>
        <div className="nav"><Database size={18}/>Incident History</div>
        <div className="nav"><BrainCircuit size={18}/>Gemini Insights</div>
      </nav>
      <div className="footnote">PROTOTYPE / DEMO ONLY<br/>Not a certified safety device</div>
    </aside>
    <main>
      <header>
        <div><div className="eyebrow">INTELLIGENT SAFETY MONITORING</div><h1>Site Command Centre</h1><p>Detect hazards. Remember near misses. Prevent repeat incidents.</p></div>
        <div className={'health '+(health?'connected':'disconnected')}>{health?<><CheckCircle2 size={16}/>API online · {health.storage_mode}</>:<><WifiOff size={16}/>API disconnected</>}</div>
      </header>
      {error&&<div className="error" role="alert">{error}</div>}
      <section className="stats">
        <div className="metric"><span>Recorded incidents<Database size={17}/></span><strong>{stats.total}</strong><small>Latest 200 events</small></div>
        <div className="metric"><span>High-priority alerts<AlertTriangle size={17}/></span><strong>{(stats.by_severity.high||0)+(stats.by_severity.critical||0)}</strong><small>High and critical events</small></div>
        <div className="metric"><span>Active history zones<HardHat size={17}/></span><strong>{Object.keys(stats.by_zone).length}</strong><small>Zones with records</small></div>
        <div className="metric"><span>Gemini insights<BrainCircuit size={17}/></span><strong>{insight?'Ready':'Idle'}</strong><small>Human-reviewed suggestions</small></div>
      </section>
      <div className="grid">
        <section className="panel">
          <div className="panel-head"><div><h2>Zone Overview</h2><p>Interactive demonstration controls</p></div><span className="pill">SIMULATED</span></div>
          <div className="zone-visual">
            <div className="zone-label">ZONE A · MOCK CUTTING STATION</div>
            <div className="zone-circle"><HardHat size={52}/><span>Restricted area</span></div>
            <div className="zone-description">Live webcam detection runs separately in the edge agent.</div>
          </div>
          <div className="actions">
            <button onClick={()=>demo('zone_entry')}>Simulate zone entry</button>
            <button className="secondary" onClick={()=>demo('prolonged_exposure')}>Simulate prolonged exposure</button>
          </div>
        </section>
        <section className="panel">
          <div className="panel-head"><div><h2>Recent Incidents</h2><p>Actual API records (including marked simulations)</p></div><button className="refresh" onClick={refresh} aria-label="Refresh"><RefreshCcw size={18}/></button></div>
          <div className="events">
            {events.length?events.map(e=><div className="event" key={e.event_id}>
              <div className={'event-badge '+e.severity}><AlertTriangle size={18}/></div>
              <div className="event-main">
                <b>{friendly(e.hazard_type)}</b>
                <span>{friendly(e.zone_id)} · {new Date(e.timestamp).toLocaleTimeString()}</span>
                <small>{e.description}</small>
              </div>
              {e.metadata?.simulated&&<em>SIM</em>}
            </div>):<div className="empty">No incidents yet. Start the demo agent or press a simulation button.</div>}
          </div>
        </section>
      </div>
      <div className="grid lower">
        <section className="panel">
          <div className="panel-head"><div><h2>Risk Pattern Breakdown</h2><p>Counted directly from incident history</p></div></div>
          {Object.keys(stats.by_hazard).length?Object.entries(stats.by_hazard).map(([k,v])=>
            <div className="bar-line" key={k}>
              <span>{friendly(k)}</span><div className="bar-track"><div style={{width:(100*v/Math.max(1,stats.total))+'%'}}/></div><b>{v}</b>
            </div>
          ):<div className="empty">Incident counts appear once the detector logs events.</div>}
        </section>
        <section className="panel">
          <div className="panel-head"><div><h2>Gemini Safety Intelligence</h2><p>Evidence-based suggestions · advisory only</p></div><BrainCircuit size={20}/></div>
          <button className="analyze" disabled={loading||events.length===0} onClick={analyze}>{loading?'Analysing...':'Analyse incidents with Gemini'}</button>
          {insight?<div className="insight"><div className="eyebrow">AI REVIEW · {insight.events_analyzed} EVENTS</div><p>{insight.summary}</p><small>{insight.model} · Verify all recommendations with a competent supervisor</small></div>:<div className="empty">Add incidents, then ask Gemini to identify patterns in real stored records. Missing API credentials produce an error rather than fabricated insights.</div>}
        </section>
      </div>
      <footer>SiteGuardian AI · Hackathon prototype · Camera and alarms require testing before any real-world use.</footer>
    </main>
  </div>
}
