import { motion, AnimatePresence } from 'framer-motion'

const TYPE_META = {
  email:      { icon: '✉️', color: 'var(--c-email)'      },
  calendar:   { icon: '📅', color: 'var(--c-schedule)'   },
  connection: { icon: '🔗', color: 'var(--c-connection)' },
  general:    { icon: '💡', color: 'var(--text-muted)'   },
}

export default function NudgeFeed({ nudges, onDismiss }) {
  if (!nudges.length) return null

  return (
    <div style={s.root}>
      <div style={s.header}>
        <span style={s.headerLabel}>Live nudges</span>
        <span style={s.count}>{nudges.length}</span>
      </div>
      <div style={s.list}>
        <AnimatePresence initial={false}>
          {nudges.map(n => (
            <motion.div
              key={n.id}
              style={s.nudge}
              initial={{ opacity: 0, x: 10, height: 0 }}
              animate={{ opacity: 1, x: 0, height: 'auto' }}
              exit={{ opacity: 0, x: 10, height: 0 }}
              transition={{ duration: 0.22, ease: 'easeOut' }}
            >
              <span style={s.icon}>{(TYPE_META[n.type] ?? TYPE_META.general).icon}</span>
              <span style={{ ...s.msg, color: (TYPE_META[n.type] ?? TYPE_META.general).color }}>
                {n.message}
              </span>
              <button style={s.dismiss} onClick={() => onDismiss(n.id)} title="Dismiss">✕</button>
            </motion.div>
          ))}
        </AnimatePresence>
      </div>
    </div>
  )
}

const s = {
  root: {
    borderTop:   '1px solid var(--border)',
    background:  'var(--surface)',
    flexShrink:   0,
    maxHeight:   '180px',
    overflowY:   'auto',
  },
  header: {
    display:     'flex',
    alignItems:  'center',
    gap:         '6px',
    padding:     '8px 16px 4px',
    position:    'sticky',
    top:          0,
    background:  'var(--surface)',
    zIndex:       1,
  },
  headerLabel: {
    fontSize: '10px', fontWeight: 700, color: 'var(--text-dim)',
    textTransform: 'uppercase', letterSpacing: '0.07em',
  },
  count: {
    background: 'var(--c-approval)', color: '#fff',
    borderRadius: '10px', padding: '1px 6px',
    fontSize: '9px', fontWeight: 700,
  },
  list: { padding: '0 12px 8px' },
  nudge: {
    display:     'flex',
    alignItems:  'flex-start',
    gap:         '7px',
    padding:     '6px 4px',
    borderBottom: '1px solid rgba(48,54,61,0.5)',
    overflow:    'hidden',
  },
  icon: { fontSize: '13px', flexShrink: 0, marginTop: '1px' },
  msg:  { fontSize: '12px', flex: 1, lineHeight: 1.45 },
  dismiss: {
    background: 'none', border: 'none', color: 'var(--text-dim)',
    cursor: 'pointer', fontSize: '10px', padding: '2px 4px',
    flexShrink: 0, fontFamily: 'inherit', lineHeight: 1,
  },
}
