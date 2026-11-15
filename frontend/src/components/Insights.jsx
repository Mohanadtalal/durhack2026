import React from 'react'
import { BrainCircuit, Loader, ShieldCheck, Sparkles } from 'lucide-react'
import { Empty } from './Common'

// Keep the AI's words as text: never interpret model output as HTML.
function inline(text) {
  return String(text).split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith('**') && part.endsWith('**')
      ? <strong key={i}>{part.slice(2, -2)}</strong>
      : part)
}

const SECTIONS = {
  SUMMARY: 'Overview',
  'MOST COMMON HAZARD': 'Most common hazard',
  'MOST AFFECTED ZONE': 'Most affected zone',
  'OBSERVED PATTERNS': 'Observed patterns',
  'POSSIBLE CONCERNS': 'Points to investigate',
  RECOMMENDATIONS: 'Recommended next steps',
  LIMITATIONS: 'What this review cannot tell us',
  'HUMAN REVIEW': 'Human review',
}
const IMPORTANT = new Set(['SUMMARY', 'RECOMMENDATIONS'])

function parseInsight(text) {
  const sections = []
  let current = null
  for (const raw of String(text || '').split(/\r?\n/)) {
    const line = raw.trim()
    if (!line) continue
    // Accept the plain text format in gemini_service.py and common Markdown variants.
    const cleaned = line.replace(/^#{1,6}\s*/, '').replace(/^\*\*(.*?)\*\*\s*$/, '$1')
    const heading = cleaned.match(/^([A-Za-z ]+):\s*(.*)$/)
    const name = heading?.[1]?.trim().toUpperCase()
    if (name && SECTIONS[name]) {
      current = { id: name, title: SECTIONS[name], items: [] }
      sections.push(current)
      if (heading[2]) current.items.push({ kind: 'text', text: heading[2] })
      continue
    }
    if (/^SITEGUARDIAN SAFETY INSIGHT:?$/i.test(cleaned)) continue
    if (!current) {
      current = { id: 'SUMMARY', title: 'Overview', items: [] }
      sections.push(current)
    }
    const bullet = line.match(/^(?:[-*•]|\d+[.)])\s+(.+)$/)
    current.items.push({ kind: bullet ? 'bullet' : 'text', text: bullet ? bullet[1] : line })
  }
  return sections.filter((section) => section.items.length)
}

function InsightSection({ section, index }) {
  const recommendations = section.id === 'RECOMMENDATIONS'
  return (
    <section className={'ai-section' + (IMPORTANT.has(section.id) ? ' ai-featured' : '')}>
      <div className="ai-section-heading">
        <span className="ai-section-number">{String(index + 1).padStart(2, '0')}</span>
        <h3>{section.title}</h3>
      </div>
      <div className="ai-section-body">
        {section.items.map((item, i) =>
          item.kind === 'bullet'
            ? <div className={'ai-point' + (recommendations ? ' ai-action' : '')} key={i}>
                <span className="ai-point-symbol">{recommendations ? <ShieldCheck size={15} /> : '•'}</span>
                <span>{inline(item.text)}</span>
              </div>
            : <p key={i}>{inline(item.text.replace(/^[-#]+\s*/, ''))}</p>)}
      </div>
    </section>
  )
}

export function InsightPanel({ insight, loading, error, canRun, onRun, generatedAt }) {
  const sections = insight ? parseInsight(insight.summary) : []
  return (
    <div className="insight-panel">
      <div className="ai-review-intro">
        <span className="ai-review-icon"><Sparkles size={20} /></span>
        <div>
          <h3>AI safety briefing</h3>
          <p>Clear observations and suggested actions from recorded incident history.</p>
        </div>
      </div>
      <button className="primary wide" disabled={loading || !canRun} onClick={onRun}>
        {loading ? <><Loader size={16} className="spin" /> Reviewing incident history…</>
          : <><BrainCircuit size={16} /> {insight ? 'Refresh AI briefing' : 'Generate AI briefing'}</>}
      </button>
      {error && <div className="error" role="alert">Could not generate the briefing. Try again. ({error})</div>}
      {insight ? (
        <article className="ai-review" aria-label="AI incident review">
          <div className="ai-meta">
            <span><strong>{insight.events_analyzed}</strong> incidents reviewed</span>
            <span>Model: {insight.model}</span>
            {generatedAt && <time dateTime={new Date(generatedAt).toISOString()}>{new Date(generatedAt).toLocaleString()}</time>}
          </div>
          <div className="ai-sections">{sections.map((section, index) =>
            <InsightSection section={section} index={index} key={section.id + index} />)}</div>
          <p className="ai-disclaimer">AI-generated advice for human review only. This prototype is not certified safety equipment. A qualified supervisor must verify the facts and decide on actions.</p>
        </article>
      ) : <Empty>{canRun
        ? 'Generate a briefing to see patterns, affected areas and prioritised actions in separate cards.'
        : 'Once a detection has been recorded, you can generate an AI briefing here.'}</Empty>}
    </div>
  )
}
