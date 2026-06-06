import { useState, useEffect, useCallback } from 'react'
import { apiFetch } from '../api.js'

const STATUS_BADGE = {
  proposed:      { label: 'Pending',          color: '#f0883e' },
  approved_by_a: { label: 'Awaiting partner', color: 'var(--c-web)' },
  approved_by_b: { label: 'Awaiting you',     color: 'var(--c-web)' },
  approved:      { label: 'Connected',        color: 'var(--c-email)' },
  rejected:      { label: 'Declined',         color: 'var(--c-error)' },
  expired:       { label: 'Expired',          color: 'var(--text-dim)' },
}

function ConfBar({ value }) {
  const pct   = Math.round((value || 0) * 100)
  const color = pct >= 75 ? 'var(--c-email)' : pct >= 50 ? 'var(--c-schedule)' : 'var(--text-dim)'
  return (
    <div style={s.barWrap}>
      <div style={{ ...s.barTrack }}>
        <div style={{ ...s.barFill, width: `${pct}%`, background: color }} />
      </div>
      <span style={{ ...s.barPct, color }}>{pct}%</span>
    </div>
  )
}

function BriefCard({ briefing, onUpdate }) {
  const [expanded, setExpanded] = useState(false)
  const [busy, setBusy]         = useState(false)
  const [feedback, setFeedback] = useState(null)

  const { proposal } = briefing
  const badge  = STATUS_BADGE[proposal.status] ?? { label: proposal.status, color: 'var(--text-dim)' }
  const canAct = !['approved', 'rejected', 'expired'].includes(proposal.status)

  async function act(action) {
    setBusy(true)
    try {
      const res  = await apiFetch(`/briefings/${briefing.id}/${action}`, { method: 'POST' })
      const data = await res.json()
      setFeedback({ ok: res.ok, msg: data.message || (res.ok ? 'Done' : data.detail) })
      onUpdate()
    } finally {
      setBusy(false)
    }
  }

  return (
    <div style={s.card}>
      <div style={s.cardTop}>
        <div style={s.cardLeft}>
          <span style={s.partnerName}>{proposal.partner_name}</span>
          <span style={{ ...s.badge, borderColor: badge.color, color: badge.color }}>{badge.label}</span>
        </div>
        <ConfBar value={proposal.confidence} />
      </div>

      <div style={s.summary}>{briefing.summary}</div>

      {proposal.proposed_collaboration && (
        <div style={s.ideaBox}>
          <span style={s.ideaLabel}>💡 Idea</span>
          <span style={s.ideaText}>{proposal.proposed_collaboration}</span>
        </div>
      )}

      <div style={s.recommendation}>{briefing.recommendation}</div>

      <button onClick={() => setExpanded(e => !e)} style={s.transcriptBtn}>
        {expanded ? '▲ Hide' : '▼ Show'} transcript ({proposal.transcript?.length ?? 0} msgs)
      </button>

      {expanded && (
        <div style={s.transcript}>
          {(proposal.transcript || []).map((m, i) => (
            <div key={i} style={s.turn}>
              <div style={{ ...s.turnRole, color: m.role === 'agent_a' ? 'var(--c-orch)' : 'var(--c-connection)' }}>
                {m.role === 'agent_a' ? '🦎 Agent A' : '🤝 Agent B'}
              </div>
              <div style={s.turnContent}>{m.content}</div>
            </div>
          ))}
        </div>
      )}

      {canAct && !feedback && (
        <div style={s.actions}>
          <button style={{ ...s.btn, ...s.btnPass }} onClick={() => act('reject')} disabled={busy}>Pass</button>
          <button style={{ ...s.btn, ...s.btnConnect }} onClick={() => act('approve')} disabled={busy}>
            {busy ? 'Processing…' : '✓ Approve'}
          </button>
        </div>
      )}
      {feedback && (
        <div style={{ fontSize: '12px', color: feedback.ok ? 'var(--c-email)' : 'var(--c-error)', textAlign: 'right' }}>
          {feedback.msg}
        </div>
      )}
    </div>
  )
}

export default function ConnectionsPanel({ agentEvents }) {
  const [briefings, setBriefings] = useState([])
  const [loading, setLoading]     = useState(true)
  const [error, setError]         = useState(null)
  const [showAll, setShowAll]     = useState(false)

  const load = useCallback(async () => {
    setLoading(true); setError(null)
    try {
      const res = await apiFetch(`/briefings?include_seen=${showAll}`)
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      setBriefings(await res.json())
    } catch (e) { setError(e.message) }
    finally     { setLoading(false) }
  }, [showAll])

  useEffect(() => { load() }, [load])

  const liveEvents = agentEvents.filter(e => e.agent === 'connection')

  return (
    <div style={s.root}>
      {/* Live events from the agent */}
      {liveEvents.length > 0 && (
        <div style={s.liveSection}>
          {liveEvents.map((e, i) => (
            <div key={i} style={s.liveRow}>
              <span style={s.liveIcon}>🔗</span>
              <span style={s.liveMsg}>{e.message}</span>
            </div>
          ))}
        </div>
      )}

      {/* Toolbar */}
      <div style={s.toolbar}>
        <label style={s.toggleLabel}>
          <input type="checkbox" checked={showAll} onChange={ev => setShowAll(ev.target.checked)} style={{ marginRight: '6px' }} />
          Show reviewed
        </label>
        <button style={s.refreshBtn} onClick={load}>↺</button>
      </div>

      {/* Briefings list */}
      <div style={s.list}>
        {loading && <div style={s.notice}>Loading…</div>}
        {error   && <div style={{ ...s.notice, color: 'var(--c-error)' }}>{error}</div>}
        {!loading && !error && briefings.length === 0 && (
          <div style={s.empty}>
            <div style={{ fontSize: '28px' }}>🔭</div>
            <div style={s.emptyText}>No matches yet</div>
            <div style={s.emptyHint}>Matchmaker runs every 60 min, or ask Jarvis to find connections.</div>
          </div>
        )}
        {!loading && briefings.map(b => <BriefCard key={b.id} briefing={b} onUpdate={load} />)}
      </div>
    </div>
  )
}

const s = {
  root: { display: 'flex', flexDirection: 'column', flex: 1, overflow: 'hidden' },
  liveSection: {
    padding: '8px 12px', borderBottom: '1px solid var(--border)',
    display: 'flex', flexDirection: 'column', gap: '4px', flexShrink: 0,
  },
  liveRow: { display: 'flex', gap: '6px', alignItems: 'flex-start' },
  liveIcon: { fontSize: '12px', flexShrink: 0 },
  liveMsg:  { fontSize: '11px', color: 'var(--c-connection)', lineHeight: 1.4 },
  toolbar: {
    display: 'flex', alignItems: 'center', justifyContent: 'space-between',
    padding: '7px 12px', borderBottom: '1px solid var(--border)', flexShrink: 0,
  },
  toggleLabel: { fontSize: '11px', color: 'var(--text-muted)', cursor: 'pointer', display: 'flex', alignItems: 'center' },
  refreshBtn: {
    background: 'none', border: 'none', color: 'var(--text-dim)',
    cursor: 'pointer', fontSize: '14px', padding: '2px 6px', fontFamily: 'inherit',
  },
  list: { flex: 1, overflowY: 'auto', padding: '10px 10px 16px', display: 'flex', flexDirection: 'column', gap: '10px' },
  notice: { textAlign: 'center', padding: '20px', color: 'var(--text-muted)', fontSize: '12px' },
  empty: { display: 'flex', flexDirection: 'column', alignItems: 'center', gap: '6px', padding: '32px 16px' },
  emptyText: { fontSize: '14px', fontWeight: 600, color: 'var(--text)' },
  emptyHint: { fontSize: '11px', color: 'var(--text-muted)', textAlign: 'center', lineHeight: 1.5 },
  card: {
    background: 'var(--surface-2)', border: '1px solid var(--border)',
    borderRadius: 'var(--radius)', padding: '12px', display: 'flex', flexDirection: 'column', gap: '8px',
  },
  cardTop: { display: 'flex', justifyContent: 'space-between', alignItems: 'center', gap: '8px', flexWrap: 'wrap' },
  cardLeft: { display: 'flex', alignItems: 'center', gap: '7px' },
  partnerName: { fontWeight: 700, fontSize: '13px', color: 'var(--text)' },
  badge: { fontSize: '10px', fontWeight: 600, border: '1px solid', borderRadius: '20px', padding: '2px 7px', letterSpacing: '0.04em' },
  barWrap: { display: 'flex', alignItems: 'center', gap: '6px' },
  barTrack: { width: '60px', height: '4px', borderRadius: '2px', background: 'var(--border)', overflow: 'hidden' },
  barFill:  { height: '4px', borderRadius: '2px', transition: 'width 0.4s' },
  barPct:   { fontSize: '10px', fontWeight: 600, flexShrink: 0 },
  summary: { fontSize: '12px', color: 'var(--text-muted)', lineHeight: 1.55 },
  ideaBox: {
    background: 'rgba(163,113,247,0.07)', border: '1px solid rgba(163,113,247,0.2)',
    borderRadius: 'var(--radius-sm)', padding: '7px 10px',
    display: 'flex', flexDirection: 'column', gap: '2px',
  },
  ideaLabel: { fontSize: '9px', fontWeight: 700, color: 'var(--c-orch)', textTransform: 'uppercase', letterSpacing: '0.06em' },
  ideaText:  { fontSize: '12px', color: 'var(--text)', lineHeight: 1.5 },
  recommendation: { fontSize: '11px', color: 'var(--text-dim)', whiteSpace: 'pre-line', lineHeight: 1.5 },
  transcriptBtn: {
    background: 'none', border: '1px solid var(--border)', color: 'var(--text-muted)',
    cursor: 'pointer', borderRadius: 'var(--radius-sm)', padding: '4px 9px',
    fontSize: '10px', fontFamily: 'inherit', alignSelf: 'flex-start',
  },
  transcript: {
    background: 'rgba(0,0,0,0.2)', borderRadius: 'var(--radius-sm)',
    padding: '10px', display: 'flex', flexDirection: 'column', gap: '10px',
    maxHeight: '200px', overflowY: 'auto',
  },
  turn: { display: 'flex', flexDirection: 'column', gap: '2px' },
  turnRole:    { fontSize: '9px', fontWeight: 700, textTransform: 'uppercase', letterSpacing: '0.05em' },
  turnContent: { fontSize: '11px', color: 'var(--text)', lineHeight: 1.5, whiteSpace: 'pre-wrap' },
  actions: { display: 'flex', gap: '7px', justifyContent: 'flex-end' },
  btn: { padding: '6px 13px', borderRadius: 'var(--radius-sm)', cursor: 'pointer', fontSize: '12px', fontWeight: 600, fontFamily: 'inherit' },
  btnPass:    { background: 'transparent', border: '1px solid var(--border)', color: 'var(--text-muted)' },
  btnConnect: { background: 'var(--c-connection)', border: 'none', color: '#fff' },
}
