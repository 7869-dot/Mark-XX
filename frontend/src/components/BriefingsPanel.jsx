import { useState, useEffect, useCallback } from 'react'

/* ── Constants ───────────────────────────────────────────────────────────── */
const AGENT_COLOR = {
  agent_a: 'var(--c-orch)',
  agent_b: 'var(--c-web)',
}

const STATUS_BADGE = {
  proposed:          { label: 'Pending review',    color: '#f0883e' },
  approved_by_a:     { label: 'Awaiting partner',  color: '#58a6ff' },
  approved_by_b:     { label: 'Awaiting you',      color: '#58a6ff' },
  approved:          { label: '✓ Connected',        color: 'var(--c-email)' },
  rejected:          { label: '✗ Declined',         color: 'var(--c-error)' },
  expired:           { label: 'Expired',            color: 'var(--text-dim)' },
}

/* ── API helpers ─────────────────────────────────────────────────────────── */
function api(path, opts = {}, userId) {
  return fetch(path, {
    ...opts,
    headers: { 'Content-Type': 'application/json', 'X-User-Id': userId, ...opts.headers },
  })
}

/* ── Sub-components ──────────────────────────────────────────────────────── */
function ConfidenceBar({ value }) {
  const pct = Math.round((value || 0) * 100)
  const color =
    pct >= 75 ? 'var(--c-email)' :
    pct >= 50 ? '#f0883e' :
    'var(--text-dim)'
  return (
    <div style={s.barWrap} title={`Confidence: ${pct}%`}>
      <div style={{ ...s.bar, width: `${pct}%`, background: color }} />
      <span style={{ ...s.barLabel, color }}>{pct}%</span>
    </div>
  )
}

function TranscriptView({ messages }) {
  if (!messages?.length) return <div style={s.noTranscript}>No transcript available.</div>
  return (
    <div style={s.transcript}>
      {messages.map((m, i) => (
        <div key={i} style={s.transcriptMsg}>
          <div style={{ ...s.transcriptRole, color: AGENT_COLOR[m.role] ?? 'var(--text-muted)' }}>
            {m.role === 'agent_a' ? '🦎 Agent A (you)' : '🤝 Agent B (them)'}
          </div>
          <div style={s.transcriptContent}>{m.content}</div>
        </div>
      ))}
    </div>
  )
}

function BriefingCard({ briefing, userId, onUpdate }) {
  const [expanded, setExpanded]   = useState(false)
  const [busy, setBusy]           = useState(false)
  const [feedback, setFeedback]   = useState(null)

  const { proposal } = briefing
  const badge = STATUS_BADGE[proposal.status] ?? { label: proposal.status, color: 'var(--text-dim)' }
  const canAct = !['approved', 'rejected', 'expired'].includes(proposal.status)

  async function act(action) {
    setBusy(true)
    try {
      const res = await api(
        `/briefings/${briefing.id}/${action}`,
        { method: 'POST' },
        userId,
      )
      const data = await res.json()
      setFeedback({ ok: res.ok, msg: data.message || (res.ok ? 'Done' : data.detail) })
      onUpdate()
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={s.card}>
      {/* Card header */}
      <div style={s.cardHeader}>
        <div style={s.cardLeft}>
          <span style={s.partnerName}>{proposal.partner_name}</span>
          <span style={{ ...s.statusBadge, borderColor: badge.color, color: badge.color }}>
            {badge.label}
          </span>
        </div>
        <ConfidenceBar value={proposal.confidence} />
      </div>

      {/* Summary */}
      <div style={s.summary}>{formatMarkdown(briefing.summary)}</div>

      {/* Collaboration idea */}
      {proposal.proposed_collaboration && (
        <div style={s.ideaBox}>
          <span style={s.ideaLabel}>💡 Proposed idea</span>
          <span style={s.ideaText}>{proposal.proposed_collaboration}</span>
        </div>
      )}

      {/* Recommendation */}
      <div style={s.recommendation}>{briefing.recommendation}</div>

      {/* Transcript toggle */}
      <button
        onClick={() => setExpanded(e => !e)}
        style={s.transcriptToggle}
      >
        {expanded ? '▲ Hide' : '▼ Show'} negotiation transcript
        ({proposal.transcript?.length ?? 0} messages)
      </button>
      {expanded && <TranscriptView messages={proposal.transcript} />}

      {/* Actions */}
      {canAct && (
        <div style={s.actions}>
          <button
            onClick={() => act('reject')}
            disabled={busy}
            style={{ ...s.btn, ...s.btnReject }}
          >
            Decline
          </button>
          <button
            onClick={() => act('approve')}
            disabled={busy}
            style={{ ...s.btn, ...s.btnApprove }}
          >
            {busy ? 'Processing…' : 'Approve connection'}
          </button>
        </div>
      )}

      {feedback && (
        <div style={{ ...s.feedback, color: feedback.ok ? 'var(--c-email)' : 'var(--c-error)' }}>
          {feedback.msg}
        </div>
      )}
    </div>
  )
}

/* ── Main panel ──────────────────────────────────────────────────────────── */
export default function BriefingsPanel({ userId, onClose }) {
  const [briefings, setBriefings] = useState([])
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState(null)
  const [showAll, setShowAll]     = useState(false)

  const load = useCallback(async () => {
    setLoading(true)
    setError(null)
    try {
      const res = await api(`/briefings?include_seen=${showAll}`, {}, userId)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setBriefings(await res.json())
    } catch (e) {
      setError(e.message)
    } finally {
      setLoading(false)
    }
  }, [userId, showAll])

  useEffect(() => { load() }, [load])

  return (
    <div style={s.overlay} onClick={e => e.target === e.currentTarget && onClose()}>
      <div style={s.panel}>
        {/* Header */}
        <div style={s.panelHeader}>
          <div>
            <div style={s.panelTitle}>🦎 Agent Briefings</div>
            <div style={s.panelSub}>
              While you were away, Axolotl found potential collaborators.
            </div>
          </div>
          <button onClick={onClose} style={s.closeBtn} aria-label="Close">✕</button>
        </div>

        {/* Toggle seen */}
        <div style={s.toolbar}>
          <label style={s.toggleLabel}>
            <input
              type="checkbox"
              checked={showAll}
              onChange={e => setShowAll(e.target.checked)}
              style={{ marginRight: '6px' }}
            />
            Show all (including reviewed)
          </label>
        </div>

        {/* Body */}
        <div style={s.body}>
          {loading && <div style={s.notice}>Loading briefings…</div>}
          {error   && <div style={{ ...s.notice, color: 'var(--c-error)' }}>Error: {error}</div>}
          {!loading && !error && briefings.length === 0 && (
            <div style={s.empty}>
              <div style={s.emptyIcon}>🔭</div>
              <div style={s.emptyText}>No new briefings</div>
              <div style={s.emptyHint}>
                {showAll
                  ? 'No matchmaking results yet. Trigger a cycle:'
                  : 'Toggle "Show all" to see past briefings, or trigger a cycle:'}
              </div>
              <code style={s.codeHint}>
                curl -X POST http://localhost:8000/admin/run-matchmaking
              </code>
            </div>
          )}
          {!loading && briefings.map(b => (
            <BriefingCard
              key={b.id}
              briefing={b}
              userId={userId}
              onUpdate={load}
            />
          ))}
        </div>
      </div>
    </div>
  )
}

/* ── Minimal markdown renderer ───────────────────────────────────────────── */
function formatMarkdown(text) {
  if (!text) return null
  return text.split('\n').map((line, i) => (
    <span key={i}>
      {line.split(/(\*\*[^*]+\*\*)/).map((part, j) =>
        part.startsWith('**') && part.endsWith('**')
          ? <strong key={j}>{part.slice(2, -2)}</strong>
          : part
      )}
      <br />
    </span>
  ))
}

/* ── Styles ──────────────────────────────────────────────────────────────── */
const s = {
  overlay: {
    position: 'fixed', inset: 0,
    background: 'rgba(0,0,0,0.6)',
    display: 'flex', alignItems: 'flex-start', justifyContent: 'flex-end',
    zIndex: 200, padding: '0',
  },
  panel: {
    width: '520px', maxWidth: '100vw', height: '100dvh',
    background: 'var(--surface)',
    borderLeft: '1px solid var(--border)',
    display: 'flex', flexDirection: 'column',
    boxShadow: '-20px 0 60px rgba(0,0,0,0.4)',
  },
  panelHeader: {
    display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start',
    padding: '20px 20px 16px',
    borderBottom: '1px solid var(--border)',
    flexShrink: 0,
  },
  panelTitle: { fontSize: '18px', fontWeight: 700, color: 'var(--c-orch)', marginBottom: '4px' },
  panelSub:   { fontSize: '12px', color: 'var(--text-muted)' },
  closeBtn: {
    background: 'none', border: 'none', color: 'var(--text-muted)',
    cursor: 'pointer', fontSize: '16px', padding: '4px', lineHeight: 1,
  },
  toolbar: {
    padding: '10px 20px',
    borderBottom: '1px solid var(--border)',
    flexShrink: 0,
  },
  toggleLabel: { fontSize: '12px', color: 'var(--text-muted)', cursor: 'pointer', display: 'flex', alignItems: 'center' },
  body: { flex: 1, overflowY: 'auto', padding: '16px 16px 24px' },

  // Empty state
  notice: { textAlign: 'center', padding: '24px', color: 'var(--text-muted)', fontSize: '13px' },
  empty: { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '8px', padding: '48px 20px' },
  emptyIcon: { fontSize: '40px' },
  emptyText: { fontSize: '16px', fontWeight: 600, color: 'var(--text)' },
  emptyHint: { fontSize: '12px', color: 'var(--text-muted)', textAlign: 'center' },
  codeHint: {
    display: 'block', marginTop: '8px', padding: '8px 12px',
    background: 'var(--surface-2)', border: '1px solid var(--border)',
    borderRadius: '6px', fontSize: '11px', color: 'var(--text-muted)',
    fontFamily: "'JetBrains Mono', monospace",
  },

  // Card
  card: {
    background: 'var(--surface-2)',
    border: '1px solid var(--border)',
    borderRadius: '10px',
    padding: '16px',
    marginBottom: '12px',
    display: 'flex', flexDirection: 'column', gap: '10px',
  },
  cardHeader: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px', flexWrap: 'wrap' },
  cardLeft: { display: 'flex', alignItems: 'center', gap: '8px' },
  partnerName: { fontWeight: 700, fontSize: '15px', color: 'var(--text)' },
  statusBadge: {
    fontSize: '10px', fontWeight: 600, border: '1px solid',
    borderRadius: '20px', padding: '2px 7px', letterSpacing: '0.04em',
  },

  // Confidence bar
  barWrap: { display: 'flex', alignItems: 'center', gap: '6px', minWidth: '80px' },
  bar: { height: '4px', borderRadius: '2px', flex: 1, background: 'var(--border)', transition: 'width 0.4s' },
  barLabel: { fontSize: '11px', fontWeight: 600, flexShrink: 0 },

  summary: { fontSize: '13px', lineHeight: 1.6, color: 'var(--text-muted)' },

  ideaBox: {
    background: 'rgba(163,113,247,0.08)',
    border: '1px solid rgba(163,113,247,0.25)',
    borderRadius: '6px', padding: '8px 12px',
    display: 'flex', flexDirection: 'column', gap: '3px',
  },
  ideaLabel: { fontSize: '10px', fontWeight: 700, color: 'var(--c-orch)', textTransform: 'uppercase', letterSpacing: '0.06em' },
  ideaText:  { fontSize: '13px', color: 'var(--text)', lineHeight: 1.5 },

  recommendation: { fontSize: '12px', color: 'var(--text-muted)', whiteSpace: 'pre-line', lineHeight: 1.5 },

  // Transcript
  transcriptToggle: {
    background: 'none', border: '1px solid var(--border)',
    color: 'var(--text-muted)', cursor: 'pointer', borderRadius: '6px',
    padding: '5px 10px', fontSize: '11px', fontFamily: 'inherit',
    alignSelf: 'flex-start',
  },
  transcript: {
    background: 'rgba(0,0,0,0.2)',
    borderRadius: '6px', padding: '12px',
    display: 'flex', flexDirection: 'column', gap: '12px',
    maxHeight: '300px', overflowY: 'auto',
  },
  noTranscript: { fontSize: '12px', color: 'var(--text-dim)', fontStyle: 'italic' },
  transcriptMsg: { display: 'flex', flexDirection: 'column', gap: '3px' },
  transcriptRole: { fontSize: '10px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' },
  transcriptContent: { fontSize: '12px', color: 'var(--text)', lineHeight: 1.5, whiteSpace: 'pre-wrap' },

  // Actions
  actions: { display: 'flex', gap: '8px', justifyContent: 'flex-end', paddingTop: '4px' },
  btn: {
    padding: '7px 16px', border: 'none', borderRadius: '6px',
    cursor: 'pointer', fontSize: '13px', fontWeight: 600, fontFamily: 'inherit',
  },
  btnApprove: { background: 'var(--c-email)', color: '#fff' },
  btnReject:  { background: 'var(--surface)', border: '1px solid var(--border)', color: 'var(--text-muted)' },

  feedback: { fontSize: '12px', textAlign: 'right', paddingTop: '2px' },
}
