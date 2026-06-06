import { AnimatePresence } from 'framer-motion'
import ProposedActionCard from './ProposedActionCard.jsx'

export default function ApprovalSurface({ actions, onApprove, onReject }) {
  const pending = actions.filter(a => a.status === 'pending')
  if (!pending.length) return null

  return (
    <div style={s.root}>
      <div style={s.header}>
        <span style={s.title}>Needs your approval</span>
        <span style={s.badge}>{pending.length}</span>
      </div>
      <div style={s.list}>
        <AnimatePresence initial={false}>
          {pending.map(action => (
            <div key={action.id} style={s.item}>
              <ProposedActionCard
                action={action}
                onApprove={onApprove}
                onReject={onReject}
              />
            </div>
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
    maxHeight:   '45%',
    display:     'flex',
    flexDirection: 'column',
    overflow:    'hidden',
  },
  header: {
    display:        'flex',
    alignItems:     'center',
    gap:            '8px',
    padding:        '10px 14px 8px',
    flexShrink:      0,
    borderBottom:   '1px solid var(--border)',
  },
  title: {
    fontSize: '11px', fontWeight: 700, color: 'var(--c-approval)',
    textTransform: 'uppercase', letterSpacing: '0.06em',
  },
  badge: {
    background: 'var(--c-approval)', color: '#fff',
    borderRadius: '10px', padding: '1px 6px',
    fontSize: '10px', fontWeight: 700,
  },
  list: {
    overflowY:   'auto',
    padding:     '10px 12px 12px',
    display:     'flex',
    flexDirection: 'column',
    gap:         '8px',
    flex:         1,
  },
  item: {},
}
