import { useState, useRef, useCallback, useEffect } from 'react'
import ChatWindow from './components/ChatWindow.jsx'
import AgentActivity from './components/AgentActivity.jsx'
import EmailConfirm from './components/EmailConfirm.jsx'
import BriefingsPanel from './components/BriefingsPanel.jsx'

/* ── User picker helpers ────────────────────────────────────────────────── */
const LS_KEY = 'axolotl_user_id'

function loadStoredUserId() {
  try { return localStorage.getItem(LS_KEY) || '' } catch { return '' }
}
function storeUserId(id) {
  try { localStorage.setItem(LS_KEY, id) } catch {}
}

/* ── Main App ────────────────────────────────────────────────────────────── */
export default function App() {
  const [messages, setMessages]       = useState([])
  const [agentEvents, setAgentEvents] = useState([])
  const [emailDraft, setEmailDraft]   = useState(null)
  const [isLoading, setIsLoading]     = useState(false)
  const [activeAgent, setActiveAgent] = useState(null)

  // A2A / user state
  const [userId, setUserId]           = useState(loadStoredUserId)
  const [users, setUsers]             = useState([])    // [{id, display_name}]
  const [briefingsOpen, setBriefingsOpen] = useState(false)
  const [unseenCount, setUnseenCount] = useState(0)

  const streamRef = useRef('')

  /* ── Load users list for picker ──────────────────────────────────────── */
  useEffect(() => {
    fetch('/users')
      .then(r => r.ok ? r.json() : [])
      .then(setUsers)
      .catch(() => {})
  }, [])

  /* ── Poll unseen briefing count when a userId is set ─────────────────── */
  useEffect(() => {
    if (!userId) { setUnseenCount(0); return }
    let active = true
    async function poll() {
      try {
        const res = await fetch('/briefings', { headers: { 'X-User-Id': userId } })
        if (res.ok && active) {
          const data = await res.json()
          setUnseenCount(data.length)
        }
      } catch {}
    }
    poll()
    const id = setInterval(poll, 30_000)
    return () => { active = false; clearInterval(id) }
  }, [userId])

  function selectUser(id) {
    setUserId(id)
    storeUserId(id)
    setUnseenCount(0)
  }

  /* ── Chat / SSE ──────────────────────────────────────────────────────── */
  const addAgentEvent = useCallback((evt) => {
    setAgentEvents(prev => [...prev, { ...evt, ts: Date.now() }])
  }, [])

  const handleEvent = useCallback((event) => {
    switch (event.type) {
      case 'agent_start':
        setActiveAgent(event.agent)
        addAgentEvent({ kind: 'start', agent: event.agent, message: event.message })
        break
      case 'agent_step':
        addAgentEvent({ kind: 'step', agent: event.agent, message: event.message })
        break
      case 'agent_result':
        addAgentEvent({ kind: 'result', agent: event.agent, message: event.message })
        break
      case 'token':
        streamRef.current += event.text
        setMessages(prev => {
          const last = prev[prev.length - 1]
          if (last?.streaming) {
            return [...prev.slice(0, -1), { ...last, content: streamRef.current }]
          }
          return [...prev, { id: 'streaming', role: 'assistant', content: streamRef.current, streaming: true }]
        })
        break
      case 'email_draft':
        setEmailDraft({ ...event.draft, draft_id: event.draft_id })
        addAgentEvent({ kind: 'draft', agent: 'email', message: 'Email draft ready — review below' })
        break
      case 'done': {
        const final = streamRef.current || event.result || ''
        streamRef.current = ''
        setMessages(prev => {
          const last = prev[prev.length - 1]
          if (last?.streaming) {
            return [...prev.slice(0, -1), { id: Date.now(), role: 'assistant', content: final, streaming: false }]
          }
          return final ? [...prev, { id: Date.now(), role: 'assistant', content: final }] : prev
        })
        setIsLoading(false)
        setActiveAgent(null)
        break
      }
      case 'error':
        streamRef.current = ''
        setMessages(prev => [
          ...prev.filter(m => !m.streaming),
          { id: Date.now(), role: 'assistant', content: `Error: ${event.message}`, isError: true },
        ])
        setIsLoading(false)
        setActiveAgent(null)
        break
    }
  }, [addAgentEvent])

  const sendMessage = useCallback(async (text) => {
    if (!text.trim() || isLoading) return
    setMessages(prev => [...prev, { id: Date.now(), role: 'user', content: text }])
    setAgentEvents([])
    setIsLoading(true)
    setActiveAgent(null)
    streamRef.current = ''

    try {
      const res = await fetch('/chat', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ message: text }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)

      const reader = res.body.getReader()
      const decoder = new TextDecoder()
      let buf = ''

      while (true) {
        const { value, done } = await reader.read()
        if (done) break
        buf += decoder.decode(value, { stream: true })
        const lines = buf.split('\n')
        buf = lines.pop()
        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try { handleEvent(JSON.parse(line.slice(6))) } catch {}
        }
      }
    } catch (err) {
      handleEvent({ type: 'error', message: err.message })
    }
  }, [isLoading, handleEvent])

  const handleEmailSend = useCallback(async (edited) => {
    try {
      const res = await fetch('/confirm-email', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(edited),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Send failed')
      setMessages(prev => [...prev, { id: Date.now(), role: 'system', content: `✓ Email sent to ${edited.to}` }])
      setEmailDraft(null)
    } catch (err) {
      alert(`Failed to send email: ${err.message}`)
    }
  }, [])

  return (
    <div style={styles.root}>
      {/* ── Header ────────────────────────────────────────────────────── */}
      <header style={styles.header}>
        <span style={styles.logo}>
          <span style={styles.logoIcon}>🦎</span>
          Axolotl
        </span>
        <span style={styles.tagline}>The next frontier of AI agents</span>

        <div style={styles.headerRight}>
          {/* User picker */}
          <UserPicker users={users} userId={userId} onSelect={selectUser} />

          {/* Briefings button */}
          {userId && (
            <button
              onClick={() => setBriefingsOpen(true)}
              style={styles.briefingsBtn}
              title="Agent briefings"
            >
              📋 Briefings
              {unseenCount > 0 && (
                <span style={styles.badge}>{unseenCount}</span>
              )}
            </button>
          )}
        </div>
      </header>

      {/* ── Main layout ───────────────────────────────────────────────── */}
      <div style={styles.main}>
        <ChatWindow messages={messages} isLoading={isLoading} onSend={sendMessage} />
        <AgentActivity events={agentEvents} activeAgent={activeAgent} />
      </div>

      {/* ── Modals ────────────────────────────────────────────────────── */}
      {emailDraft && (
        <EmailConfirm
          draft={emailDraft}
          onSend={handleEmailSend}
          onCancel={() => setEmailDraft(null)}
        />
      )}

      {briefingsOpen && userId && (
        <BriefingsPanel
          userId={userId}
          onClose={() => { setBriefingsOpen(false); setUnseenCount(0) }}
        />
      )}
    </div>
  )
}

/* ── User Picker component ──────────────────────────────────────────────── */
function UserPicker({ users, userId, onSelect }) {
  const current = users.find(u => u.id === userId)

  if (!users.length) {
    return (
      <div style={styles.pickerEmpty}>
        No users seeded — run <code>python scripts/seed_agents.py</code>
      </div>
    )
  }

  return (
    <div style={styles.pickerWrap}>
      <span style={styles.pickerLabel}>Browsing as:</span>
      <select
        value={userId}
        onChange={e => onSelect(e.target.value)}
        style={styles.pickerSelect}
      >
        <option value="">— select user —</option>
        {users.map(u => (
          <option key={u.id} value={u.id}>{u.display_name}</option>
        ))}
      </select>
    </div>
  )
}

/* ── Styles ─────────────────────────────────────────────────────────────── */
const styles = {
  root: {
    display: 'flex', flexDirection: 'column',
    height: '100dvh', background: 'var(--bg)', overflow: 'hidden',
  },
  header: {
    display: 'flex', alignItems: 'center', gap: '12px',
    padding: '0 20px', height: '52px',
    borderBottom: '1px solid var(--border)',
    background: 'var(--surface)', flexShrink: 0,
  },
  logo: {
    display: 'flex', alignItems: 'center', gap: '8px',
    fontWeight: 700, fontSize: '17px', color: 'var(--c-orch)', letterSpacing: '-0.3px',
  },
  logoIcon: { fontSize: '20px' },
  tagline: { fontSize: '12px', color: 'var(--text-muted)', marginRight: 'auto' },

  headerRight: { display: 'flex', alignItems: 'center', gap: '10px', marginLeft: 'auto' },

  pickerWrap:  { display: 'flex', alignItems: 'center', gap: '6px' },
  pickerLabel: { fontSize: '11px', color: 'var(--text-muted)', whiteSpace: 'nowrap' },
  pickerSelect: {
    background: 'var(--surface-2)', border: '1px solid var(--border)',
    color: 'var(--text)', borderRadius: '6px', padding: '4px 8px',
    fontSize: '12px', cursor: 'pointer', fontFamily: 'inherit',
  },
  pickerEmpty: {
    fontSize: '11px', color: 'var(--text-dim)',
    background: 'var(--surface-2)', borderRadius: '6px',
    padding: '4px 8px', border: '1px solid var(--border)',
  },

  briefingsBtn: {
    display: 'flex', alignItems: 'center', gap: '6px',
    background: 'var(--surface-2)', border: '1px solid var(--border)',
    color: 'var(--text)', borderRadius: '6px', padding: '5px 10px',
    fontSize: '12px', cursor: 'pointer', fontFamily: 'inherit',
    position: 'relative',
  },
  badge: {
    background: 'var(--c-orch)', color: '#fff',
    borderRadius: '10px', padding: '1px 6px',
    fontSize: '10px', fontWeight: 700, minWidth: '16px', textAlign: 'center',
  },

  main: { display: 'flex', flex: 1, overflow: 'hidden' },
}
