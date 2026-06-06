import { useState } from 'react'
import { motion, AnimatePresence } from 'framer-motion'

function AgendaItem({ item }) {
  const time = item.time || item.start || ''
  const formatted = time
    ? new Date(time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit' })
    : ''
  return (
    <div style={s.agendaItem}>
      {formatted && <span style={s.agendaTime}>{formatted}</span>}
      <span style={s.agendaTitle}>{item.title || item.summary}</span>
      {item.note && <span style={s.agendaNote}>{item.note}</span>}
    </div>
  )
}

const TONE_COLOR = {
  calm:   'var(--c-email)',
  busy:   'var(--c-schedule)',
  hectic: 'var(--c-error)',
}

export default function BriefingCard({ briefing, onDismiss }) {
  const [collapsed, setCollapsed] = useState(false)

  const tone      = briefing.tone || 'calm'
  const toneColor = TONE_COLOR[tone] ?? 'var(--c-email)'
  const agenda    = briefing.agenda || []

  return (
    <motion.div
      style={s.card}
      initial={{ opacity: 0, y: -8 }}
      animate={{ opacity: 1, y: 0 }}
      transition={{ duration: 0.35, ease: 'easeOut' }}
    >
      {/* Header row */}
      <div style={s.header}>
        <div style={s.headerLeft}>
          <span style={{ ...s.tonePip, background: toneColor }} />
          <span style={s.label}>Morning briefing</span>
          <span style={{ ...s.toneBadge, color: toneColor, borderColor: toneColor }}>
            {tone}
          </span>
        </div>
        <div style={s.headerActions}>
          <button style={s.iconBtn} onClick={() => setCollapsed(c => !c)} title={collapsed ? 'Expand' : 'Collapse'}>
            {collapsed ? '▼' : '▲'}
          </button>
          {onDismiss && (
            <button style={s.iconBtn} onClick={onDismiss} title="Dismiss briefing">✕</button>
          )}
        </div>
      </div>

      <AnimatePresence initial={false}>
        {!collapsed && (
          <motion.div
            key="body"
            initial={{ opacity: 0, height: 0 }}
            animate={{ opacity: 1, height: 'auto' }}
            exit={{ opacity: 0, height: 0 }}
            transition={{ duration: 0.25, ease: 'easeInOut' }}
            style={{ overflow: 'hidden' }}
          >
            {/* Greeting */}
            <p style={s.greeting}>{briefing.greeting}</p>

            {/* Agenda */}
            {agenda.length > 0 && (
              <div style={s.section}>
                <div style={s.sectionLabel}>📅 Today</div>
                <div style={s.agendaList}>
                  {agenda.map((item, i) => <AgendaItem key={i} item={item} />)}
                </div>
              </div>
            )}

            {/* Email summary */}
            {briefing.email_summary && (
              <div style={s.section}>
                <div style={s.sectionLabel}>✉️ Inbox</div>
                <p style={s.emailSummary}>{briefing.email_summary}</p>
              </div>
            )}

            {/* Connections */}
            {briefing.connection_count > 0 && (
              <div style={s.connectionPill}>
                <span style={s.connectionDot} />
                {briefing.connection_count} new connection{briefing.connection_count > 1 ? 's' : ''} waiting
              </div>
            )}
          </motion.div>
        )}
      </AnimatePresence>
    </motion.div>
  )
}

const s = {
  card: {
    background:   'var(--surface)',
    borderBottom: '1px solid var(--border)',
    padding:      '12px 16px',
    flexShrink:    0,
  },
  header: {
    display:        'flex',
    alignItems:     'center',
    justifyContent: 'space-between',
    marginBottom:   '8px',
  },
  headerLeft: {
    display:    'flex',
    alignItems: 'center',
    gap:        '7px',
  },
  headerActions: { display: 'flex', gap: '4px' },
  tonePip: {
    width: '6px', height: '6px', borderRadius: '50%', flexShrink: 0,
  },
  label: { fontSize: '11px', fontWeight: 600, color: 'var(--text-muted)', textTransform: 'uppercase', letterSpacing: '0.06em' },
  toneBadge: {
    fontSize: '10px', fontWeight: 600, border: '1px solid',
    borderRadius: '20px', padding: '1px 6px', letterSpacing: '0.04em',
  },
  iconBtn: {
    background: 'none', border: 'none', color: 'var(--text-dim)',
    cursor: 'pointer', fontSize: '11px', padding: '2px 5px',
    fontFamily: 'inherit', lineHeight: 1,
  },
  greeting: {
    fontSize: '13px', color: 'var(--text)', lineHeight: 1.6,
    marginBottom: '10px',
  },
  section: { marginBottom: '10px' },
  sectionLabel: {
    fontSize: '10px', fontWeight: 700, color: 'var(--text-dim)',
    textTransform: 'uppercase', letterSpacing: '0.07em', marginBottom: '5px',
  },
  agendaList: { display: 'flex', flexDirection: 'column', gap: '4px' },
  agendaItem: {
    display: 'flex', alignItems: 'baseline', gap: '8px',
    fontSize: '12px',
  },
  agendaTime:  { color: 'var(--c-schedule)', fontWeight: 600, flexShrink: 0, minWidth: '40px', fontSize: '11px' },
  agendaTitle: { color: 'var(--text)' },
  agendaNote:  { color: 'var(--text-muted)', fontSize: '11px' },
  emailSummary: { fontSize: '12px', color: 'var(--text-muted)', lineHeight: 1.55 },
  connectionPill: {
    display:     'inline-flex',
    alignItems:  'center',
    gap:         '6px',
    fontSize:    '11px',
    color:       'var(--c-connection)',
    background:  'rgba(6,182,212,0.08)',
    border:      '1px solid rgba(6,182,212,0.25)',
    borderRadius: '20px',
    padding:     '3px 10px',
    marginTop:   '2px',
  },
  connectionDot: {
    width: '5px', height: '5px', borderRadius: '50%',
    background: 'var(--c-connection)', flexShrink: 0,
    animation: 'pulse 1.5s ease-in-out infinite',
  },
}
