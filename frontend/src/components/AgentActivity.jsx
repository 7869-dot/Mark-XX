import { useEffect, useRef } from 'react'

const AGENT_META = {
  orchestrator: { label: 'Orchestrator', color: 'var(--c-orch)',  icon: '🦎' },
  web:          { label: 'Web Agent',    color: 'var(--c-web)',   icon: '🌐' },
  email:        { label: 'Email Agent',  color: 'var(--c-email)', icon: '✉️' },
}

const KIND_STYLE = {
  start:  { prefix: '▶',  color: 'var(--text)' },
  step:   { prefix: '·',  color: 'var(--text-muted)' },
  result: { prefix: '✓',  color: 'var(--c-email)' },
  draft:  { prefix: '📋', color: 'var(--c-email)' },
}

export default function AgentActivity({ events, activeAgent }) {
  const bottomRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [events])

  return (
    <div style={styles.root}>
      <div style={styles.header}>
        <span style={styles.headerTitle}>Agent Activity</span>
        {activeAgent && (
          <ActivePill agent={activeAgent} />
        )}
      </div>

      <div style={styles.feed}>
        {events.length === 0 && (
          <div style={styles.empty}>
            Activity will appear here as agents work…
          </div>
        )}

        {events.map((evt, i) => (
          <EventRow key={i} event={evt} />
        ))}
        <div ref={bottomRef} />
      </div>

      {/* Agent legend */}
      <div style={styles.legend}>
        {Object.entries(AGENT_META).map(([key, meta]) => (
          <div key={key} style={styles.legendItem}>
            <span style={{ ...styles.dot, background: meta.color }} />
            <span style={styles.legendLabel}>{meta.label}</span>
          </div>
        ))}
      </div>
    </div>
  )
}

function ActivePill({ agent }) {
  const meta = AGENT_META[agent] ?? { label: agent, color: 'var(--text-muted)', icon: '?' }
  return (
    <div style={{ ...styles.pill, borderColor: meta.color, color: meta.color }}>
      <span style={styles.pulsingDot(meta.color)} />
      {meta.icon} {meta.label}
    </div>
  )
}

function EventRow({ event }) {
  const meta  = AGENT_META[event.agent] ?? { label: event.agent, color: 'var(--text-muted)', icon: '?' }
  const kstyle = KIND_STYLE[event.kind] ?? { prefix: '·', color: 'var(--text-dim)' }

  return (
    <div style={styles.row}>
      <span style={{ ...styles.prefix, color: kstyle.color }}>{kstyle.prefix}</span>
      <div style={styles.rowBody}>
        <span style={{ ...styles.agentTag, color: meta.color }}>{meta.icon} {meta.label}</span>
        <span style={{ ...styles.rowMsg, color: kstyle.color }}>{event.message}</span>
      </div>
    </div>
  )
}

const styles = {
  root: {
    width: '320px',
    flexShrink: 0,
    display: 'flex',
    flexDirection: 'column',
    background: 'var(--surface)',
    overflow: 'hidden',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
    padding: '12px 16px',
    borderBottom: '1px solid var(--border)',
    flexShrink: 0,
    gap: '8px',
  },
  headerTitle: {
    fontSize: '12px',
    fontWeight: 600,
    color: 'var(--text-muted)',
    textTransform: 'uppercase',
    letterSpacing: '0.06em',
  },
  pill: {
    display: 'flex',
    alignItems: 'center',
    gap: '5px',
    fontSize: '11px',
    fontWeight: 600,
    border: '1px solid',
    borderRadius: '20px',
    padding: '2px 8px',
  },
  pulsingDot: (color) => ({
    width: '6px',
    height: '6px',
    borderRadius: '50%',
    background: color,
    display: 'inline-block',
    animation: 'pulse 1.5s ease-in-out infinite',
  }),
  feed: {
    flex: 1,
    overflowY: 'auto',
    padding: '12px 8px',
    display: 'flex',
    flexDirection: 'column',
    gap: '4px',
  },
  empty: {
    color: 'var(--text-dim)',
    fontSize: '12px',
    textAlign: 'center',
    marginTop: '24px',
    padding: '0 16px',
  },
  row: {
    display: 'flex',
    gap: '8px',
    padding: '4px 8px',
    borderRadius: 'var(--radius-sm)',
    alignItems: 'flex-start',
  },
  prefix: {
    fontSize: '13px',
    lineHeight: 1.5,
    flexShrink: 0,
    marginTop: '1px',
  },
  rowBody: {
    display: 'flex',
    flexDirection: 'column',
    gap: '1px',
    minWidth: 0,
  },
  agentTag: {
    fontSize: '10px',
    fontWeight: 600,
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
    flexShrink: 0,
  },
  rowMsg: {
    fontSize: '12px',
    lineHeight: 1.4,
    wordBreak: 'break-word',
  },
  legend: {
    display: 'flex',
    gap: '12px',
    padding: '10px 16px',
    borderTop: '1px solid var(--border)',
    flexShrink: 0,
    flexWrap: 'wrap',
  },
  legendItem: {
    display: 'flex',
    alignItems: 'center',
    gap: '5px',
  },
  dot: {
    width: '8px',
    height: '8px',
    borderRadius: '50%',
    flexShrink: 0,
  },
  legendLabel: {
    fontSize: '11px',
    color: 'var(--text-muted)',
  },
}

// Pulse keyframe
if (typeof document !== 'undefined' && !document.getElementById('axo-pulse')) {
  const s = document.createElement('style')
  s.id = 'axo-pulse'
  s.textContent = `@keyframes pulse { 0%,100%{opacity:1} 50%{opacity:0.3} }`
  document.head.appendChild(s)
}
