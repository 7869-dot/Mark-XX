import { useState } from 'react'
import { motion } from 'framer-motion'

/* ── Email reply card ──────────────────────────────────────────────────── */
function EmailCard({ action, onApprove, onReject }) {
  const { payload, rationale } = action
  const [body, setBody]         = useState(payload.body || '')
  const [busy, setBusy]         = useState(false)
  const [feedback, setFeedback] = useState(null)

  async function approve() {
    setBusy(true)
    try {
      await onApprove(action.id, { ...payload, body })
      setFeedback({ ok: true, msg: 'Email sent.' })
    } catch (e) {
      setFeedback({ ok: false, msg: e.message })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={s.card}>
      <div style={s.cardTag('var(--c-email)')}>✉️ Email reply proposed</div>
      <div style={s.meta}>
        <span style={s.metaLabel}>To</span>
        <span style={s.metaVal}>{payload.to}</span>
      </div>
      <div style={s.meta}>
        <span style={s.metaLabel}>Subject</span>
        <span style={s.metaVal}>{payload.subject}</span>
      </div>
      {rationale && <div style={s.rationale}>{rationale}</div>}
      <textarea
        style={s.bodyArea}
        value={body}
        onChange={e => setBody(e.target.value)}
        rows={5}
        placeholder="Edit reply…"
        disabled={busy || !!feedback?.ok}
      />
      {feedback ? (
        <div style={{ ...s.feedback, color: feedback.ok ? 'var(--c-email)' : 'var(--c-error)' }}>
          {feedback.msg}
        </div>
      ) : (
        <div style={s.actions}>
          <button style={{ ...s.btn, ...s.btnGhost }} onClick={() => onReject(action.id)} disabled={busy}>
            Discard
          </button>
          <button style={{ ...s.btn, ...s.btnApprove('var(--c-email)') }} onClick={approve} disabled={busy || !body.trim()}>
            {busy ? 'Sending…' : '↑ Send reply'}
          </button>
        </div>
      )}
    </div>
  )
}

/* ── Calendar event card ───────────────────────────────────────────────── */
function CalendarCard({ action, onApprove, onReject }) {
  const { payload, rationale } = action
  const [busy, setBusy]         = useState(false)
  const [feedback, setFeedback] = useState(null)

  function fmt(iso) {
    if (!iso) return ''
    try { return new Date(iso).toLocaleString([], { dateStyle: 'medium', timeStyle: 'short' }) }
    catch { return iso }
  }

  async function approve() {
    setBusy(true)
    try {
      await onApprove(action.id)
      setFeedback({ ok: true, msg: 'Event added to calendar.' })
    } catch (e) {
      setFeedback({ ok: false, msg: e.message })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={s.card}>
      <div style={s.cardTag('var(--c-schedule)')}>📅 Calendar event proposed</div>
      <div style={s.eventTitle}>{payload.title}</div>
      <div style={s.meta}>
        <span style={s.metaLabel}>When</span>
        <span style={s.metaVal}>{fmt(payload.start)} → {fmt(payload.end)}</span>
      </div>
      {payload.attendees?.length > 0 && (
        <div style={s.meta}>
          <span style={s.metaLabel}>With</span>
          <span style={s.metaVal}>{payload.attendees.join(', ')}</span>
        </div>
      )}
      {payload.description && <div style={s.desc}>{payload.description}</div>}
      {rationale && <div style={s.rationale}>{rationale}</div>}
      {feedback ? (
        <div style={{ ...s.feedback, color: feedback.ok ? 'var(--c-email)' : 'var(--c-error)' }}>
          {feedback.msg}
        </div>
      ) : (
        <div style={s.actions}>
          <button style={{ ...s.btn, ...s.btnGhost }} onClick={() => onReject(action.id)} disabled={busy}>
            Decline
          </button>
          <button style={{ ...s.btn, ...s.btnApprove('var(--c-schedule)') }} onClick={approve} disabled={busy}>
            {busy ? 'Adding…' : '✓ Add to calendar'}
          </button>
        </div>
      )}
    </div>
  )
}

/* ── Connection approval card ─────────────────────────────────────────── */
function ConnectionCard({ action, onApprove, onReject }) {
  const { payload, rationale } = action
  const [busy, setBusy]         = useState(false)
  const [feedback, setFeedback] = useState(null)

  async function approve() {
    setBusy(true)
    try {
      await onApprove(action.id)
      setFeedback({ ok: true, msg: 'Connection approved.' })
    } catch (e) {
      setFeedback({ ok: false, msg: e.message })
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={s.card}>
      <div style={s.cardTag('var(--c-connection)')}>🔗 Connection proposed</div>
      <div style={s.eventTitle}>{payload.partner_name}</div>
      {payload.summary && <div style={s.desc}>{payload.summary}</div>}
      {rationale && <div style={s.rationale}>{rationale}</div>}
      <div style={s.mutualNote}>
        ℹ️ Contact details shared only after <strong>mutual approval</strong>.
      </div>
      {feedback ? (
        <div style={{ ...s.feedback, color: feedback.ok ? 'var(--c-email)' : 'var(--c-error)' }}>
          {feedback.msg}
        </div>
      ) : (
        <div style={s.actions}>
          <button style={{ ...s.btn, ...s.btnGhost }} onClick={() => onReject(action.id)} disabled={busy}>
            Pass
          </button>
          <button style={{ ...s.btn, ...s.btnApprove('var(--c-connection)') }} onClick={approve} disabled={busy}>
            {busy ? 'Processing…' : '✓ Connect'}
          </button>
        </div>
      )}
    </div>
  )
}

/* ── Dispatcher ───────────────────────────────────────────────────────── */
export default function ProposedActionCard({ action, onApprove, onReject }) {
  return (
    <motion.div
      layout
      initial={{ opacity: 0, y: 6 }}
      animate={{ opacity: 1, y: 0 }}
      exit={{ opacity: 0, scale: 0.96 }}
      transition={{ duration: 0.2 }}
    >
      {action.type === 'email_reply'         && <EmailCard      action={action} onApprove={onApprove} onReject={onReject} />}
      {action.type === 'calendar_event'      && <CalendarCard   action={action} onApprove={onApprove} onReject={onReject} />}
      {action.type === 'connection_approval' && <ConnectionCard action={action} onApprove={onApprove} onReject={onReject} />}
    </motion.div>
  )
}

/* ── Styles ───────────────────────────────────────────────────────────── */
const s = {
  card: {
    background:   'var(--surface-2)',
    border:       '1px solid var(--border)',
    borderRadius: 'var(--radius)',
    padding:      '12px 14px',
    display:      'flex',
    flexDirection: 'column',
    gap:          '8px',
  },
  cardTag: (color) => ({
    fontSize: '10px', fontWeight: 700, color,
    textTransform: 'uppercase', letterSpacing: '0.07em',
  }),
  eventTitle: { fontSize: '14px', fontWeight: 700, color: 'var(--text)' },
  meta: { display: 'flex', gap: '8px', fontSize: '12px', alignItems: 'baseline' },
  metaLabel: { color: 'var(--text-dim)', fontWeight: 600, flexShrink: 0, minWidth: '46px' },
  metaVal:   { color: 'var(--text-muted)', wordBreak: 'break-word' },
  desc:      { fontSize: '12px', color: 'var(--text-muted)', lineHeight: 1.5 },
  rationale: {
    fontSize: '11px', color: 'var(--text-dim)', fontStyle: 'italic',
    borderLeft: '2px solid var(--border)', paddingLeft: '8px',
  },
  bodyArea: {
    width: '100%', resize: 'vertical',
    background: 'var(--surface)', border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm)', color: 'var(--text)',
    fontFamily: "'JetBrains Mono', monospace", fontSize: '12px',
    padding: '8px', lineHeight: 1.55, outline: 'none',
  },
  mutualNote: {
    fontSize: '11px', color: 'var(--text-dim)',
    background: 'rgba(6,182,212,0.06)',
    border: '1px solid rgba(6,182,212,0.15)',
    borderRadius: 'var(--radius-sm)', padding: '6px 10px',
  },
  actions: { display: 'flex', gap: '8px', justifyContent: 'flex-end' },
  btn: {
    padding: '6px 14px', borderRadius: 'var(--radius-sm)',
    cursor: 'pointer', fontSize: '12px', fontWeight: 600, fontFamily: 'inherit',
  },
  btnGhost: {
    background: 'transparent', border: '1px solid var(--border)', color: 'var(--text-muted)',
  },
  btnApprove: (color) => ({
    background: color, border: 'none', color: '#fff',
  }),
  feedback: { fontSize: '12px', textAlign: 'right' },
}
