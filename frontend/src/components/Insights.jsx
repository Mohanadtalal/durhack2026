import React from 'react'
import { BrainCircuit, Loader } from 'lucide-react'
import { Empty } from './Common'

// Render **bold** without dangerouslySetInnerHTML.
function inline(text) {
  return text.split(/(\*\*[^*]+\*\*)/g).map((part, i) =>
    part.startsWith('**') && part.endsWith('**') ? <strong key={i}>{part.slice(2, -2)}</strong> : part)
}

function SummaryText({ text }) {
  const blocks = []
  let list = null
  text.split('\n').forEach((raw, i) => {
    const line = raw.trim()
    const m = line.match(/^(?:[-*•]|\d+[.)])\s+(.*)/)
    if (m) {
      if (!list) { list = []; blocks.push({ type: 'ul', items: list }) }
      list.push(m[1])
    } else if (line) {
      list = null
      blocks.push({ type: 'p', text: line.replace(/^#+\s*/, '') })
    }
  })
  return blocks.map((b, i) => b.type === 'ul'
    ? <ul key={i}>{b.items.map((t, j) => <li key={j}>{inline(t)}</li>)}</ul>
    : <p key={i}>{inline(b.text)}</p>)
}

export function InsightPanel({ insight, loading, error, canRun, onRun, generatedAt }) {
  return (
    <div className="insight-panel">
      <button className="primary wide" disabled={loading || !canRun} onClick={onRun}>
        {loading ? <><Loader size={16} className="spin" /> Reading the incident history…</> : <><BrainCircuit size={16} /> Ask Gemini to review the incidents</>}
      </button>
      {error && <div className="error" role="alert">The AI review didn't work this time. You can try again. ({error})</div>}
      {insight
        ? <article className="insight">
            <div className="insight-meta">
              <span>{insight.events_analyzed} incidents read</span>
              <span>{insight.model}</span>
              {generatedAt && <span>{new Date(generatedAt).toLocaleTimeString()}</span>}
            </div>
            <SummaryText text={insight.summary} />
            <p className="insight-note">AI suggestion for human review. Check every recommendation with a competent supervisor.</p>
          </article>
        : <Empty>{canRun ? 'Press the button above. Gemini will read the saved incidents and explain, in plain words, where problems keep happening.' : 'There is nothing to review yet. Once incidents have been recorded (or you make a practice one on the Overview page), the button above will work.'}</Empty>}
    </div>
  )
}
