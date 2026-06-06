import { useState, useRef, useEffect } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import ApprovalSurface from './ApprovalSurface.jsx'
import ConnectionsPanel from './ConnectionsPanel.jsx'

/* ── Agent config — add a 4th entry here to surface a new agent ──────── */
export const SUB_AGENTS = [
  { id: 'web',        label: 'Web',             color: 'var(--c-web)',        icon: '🌐' },
  { id: 'schedule',   label: 'Email & Sched.',  color: 'var(--c-schedule)',   icon: '📅' },
  { id: 'connection', label: 'Connections',     color: 'var(--c-connection)', icon: '🔗' },
]

/* ── Generic activity feed (used for Web + Schedule tabs) ────────────── */
function ActivityFeed({ events, agent }) {
  const bottomRef = useRef(null)
  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [events])

  const meta = SUB_AGENTS.find(a => a.id === agent) ?? { color: 'var(--text-muted)', icon: '?' }

  const KIND = {
    start:  { prefix: '▶', color: 'var(--text)' },
    step:   { prefix: '·', color: 'var(--text-muted)' },
    result: { prefix: '✓', color: meta.color },
    draft:  { prefix: '📋', color: meta.color },
  }

  return (
    <div style={s.feed}>
      {events.length === 0 && (
        <div style={s.empty}>
          {meta.icon} {agent === 'web' ? 'Web searches and page reads appear here.' :
            agent === 'schedule' ? 'Email and calendar activity appears here.' : 'Activity appears here.'}
        </div>
      )}
      {events.map((evt, i) => {
        const k = KIND[evt.kind] ?? { prefix: '·', color: 'var(--text-dim)' }
        return (
          <div key={i} style={s.row}>
            <span style={{ ...s.prefix, color: k.color }}>{k.prefix}</span>
            <span style={{ ...s.msg, color: k.color }}>{evt.message}</span>
          </div>
        )
      })}
      <div ref={bottomRef} />
    </div>
  )
}

/* ── Main component ──────────────────────────────────────────────────── */
export default function SubAgentTabs({
  agentEvents,
  proposedActions,
  onApprove,
  onReject,
}) {
  const [active, setActive] = useState('web')

  const filtered = agentEvents.filter(e =>
    e.agent === active || (active === 'web' && e.agent === 'orchestrator')
  )

  return (
    <div style={s.root}>
      {/* Tab bar */}
      <div style={s.tabBar}>
        {SUB_AGENTS.map(agent => {
          const isActive   = active === agent.id
          const liveCount  = agentEvents.filter(e => e.agent === agent.id).length
          return (
            <button
              key={agent.id}
              style={{
                ...s.tab,
                ...(isActive ? { ...s.tabActive, borderBottomColor: agent.color, color: agent.color } : {}),
              }}
              onClick={() => setActive(agent.id)}
            >
              {agent.icon} {agent.label}
              {liveCount > 0 && !isActive && (
                <span style={{ ...s.livePip, background: agent.color }} />
              )}
            </button>
          )
        })}
      </div>

      {/* Panel area */}
      <div style={s.panelArea}>
        <AnimatePresence mode="wait" initial={false}>
          <motion.div
            key={active}
            style={s.panel}
            initial={{ opacity: 0, x: 6 }}
            animate={{ opacity: 1, x: 0 }}
            exit={{ opacity: 0, x: -6 }}
            transition={{ duration: 0.18, ease: 'easeInOut' }}
          >
            {active === 'connection' ? (
              <ConnectionsPanel agentEvents={agentEvents} />
            ) : (
              <ActivityFeed events={filtered} agent={active} />
            )}
          </motion.div>
        </AnimatePresence>
      </div>

      {/* Approval surface — always visible below panels */}
      <ApprovalSurface
        actions={proposedActions}
        onApprove={onApprove}
        onReject={onReject}
      />
    </div>
  )
}

const s = {
  root: {
    display:        'flex',
    flexDirection:  'column',
    flex:            1,
    overflow:       'hidden',
    background:     'var(--surface)',
  },
  tabBar: {
    display:        'flex',
    borderBottom:   '1px solid var(--border)',
    flexShrink:      0,
    overflowX:      'auto',
  },
  tab: {
    display:        'flex',
    alignItems:     'center',
    gap:            '5px',
    padding:        '10px 14px',
    background:     'none',
    border:         'none',
    borderBottom:   '2px solid transparent',
    color:          'var(--text-muted)',
    cursor:         'pointer',
    fontSize:       '12px',
    fontFamily:     'inherit',
    fontWeight:      500,
    whiteSpace:     'nowrap',
    transition:     'color 0.15s, border-color 0.15s',
  },
  tabActive: {
    fontWeight: 600,
  },
  livePip: {
    width: '5px', height: '5px', borderRadius: '50%',
    animation: 'pulse 1.5s ease-in-out infinite',
  },
  panelArea: {
    flex:    1,
    overflow: 'hidden',
    position: 'relative',
    minHeight: '120px',
  },
  panel: {
    position:  'absolute',
    inset:      0,
    display:   'flex',
    flexDirection: 'column',
    overflow:  'hidden',
  },
  feed: {
    flex:     1,
    overflowY: 'auto',
    padding:  '10px 12px',
    display:  'flex',
    flexDirection: 'column',
    gap:      '3px',
  },
  empty: {
    color:    'var(--text-dim)',
    fontSize: '12px',
    textAlign: 'center',
    marginTop: '24px',
    padding:  '0 16px',
    lineHeight: 1.5,
  },
  row: {
    display:  'flex',
    gap:      '7px',
    padding:  '3px 4px',
    alignItems: 'flex-start',
  },
  prefix: { fontSize: '12px', flexShrink: 0, lineHeight: 1.5, marginTop: '1px' },
  msg:    { fontSize: '12px', lineHeight: 1.45, wordBreak: 'break-word', flex: 1 },
}
