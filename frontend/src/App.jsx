import { useState, useRef, useCallback, useEffect } from 'react'
import ChatWindow from './components/ChatWindow.jsx'
import AgentActivity from './components/AgentActivity.jsx'
import EmailConfirm from './components/EmailConfirm.jsx'
import BriefingsPanel from './components/BriefingsPanel.jsx'
import LoginPage from './components/LoginPage.jsx'
import { getJwt, setJwt, clearJwt, isAuthenticated, authHeaders, apiFetch } from './api.js'

export default function App() {
  /* ── Auth state ──────────────────────────────────────────────────────── */
  const [authReady, setAuthReady]   = useState(false)   // finished checking JWT
  const [user, setUser]             = useState(null)     // {id, display_name, email}

  /* ── Chat state ──────────────────────────────────────────────────────── */
  const [messages, setMessages]     = useState([])
  const [agentEvents, setAgentEvents] = useState([])
  const [emailDraft, setEmailDraft] = useState(null)
  const [isLoading, setIsLoading]   = useState(false)
  const [activeAgent, setActiveAgent] = useState(null)
  const streamRef = useRef('')

  /* ── Briefings state ─────────────────────────────────────────────────── */
  const [briefingsOpen, setBriefingsOpen] = useState(false)
  const [unseenCount, setUnseenCount]     = useState(0)

  /* ── 1. On mount: harvest token from URL or check localStorage ───────── */
  useEffect(() => {
    const params = new URLSearchParams(window.location.search)
    const urlToken = params.get('token')
    if (urlToken) {
      setJwt(urlToken)
      // Remove token from URL so it's not in browser history
      window.history.replaceState({}, '', window.location.pathname)
    }

    if (isAuthenticated()) {
      fetchMe()
    } else {
      setAuthReady(true)
    }
  }, [])

  async function fetchMe() {
    try {
      const res = await apiFetch('/auth/me')
      if (res.ok) {
        setUser(await res.json())
      } else {
        // JWT might be expired — clear it and show login
        clearJwt()
      }
    } catch {
      clearJwt()
    } finally {
      setAuthReady(true)
    }
  }

  function handleLogout() {
    clearJwt()
    setUser(null)
    setMessages([])
    setAgentEvents([])
  }

  /* ── 2. Poll unseen briefings count ──────────────────────────────────── */
  useEffect(() => {
    if (!user) { setUnseenCount(0); return }
    let active = true

    async function poll() {
      try {
        const res = await apiFetch('/briefings')
        if (res.ok && active) setUnseenCount((await res.json()).length)
      } catch {}
    }

    poll()
    const id = setInterval(poll, 30_000)
    return () => { active = false; clearInterval(id) }
  }, [user])

  /* ── 3. Chat / SSE ───────────────────────────────────────────────────── */
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
        headers: authHeaders(),
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
        headers: authHeaders(),
        body: JSON.stringify(edited),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Send failed')
      setMessages(prev => [...prev, { id: Date.now(), role: 'system', content: `Email sent to ${edited.to}` }])
      setEmailDraft(null)
    } catch (err) {
      alert(`Failed to send email: ${err.message}`)
    }
  }, [])

  /* ── Render ──────────────────────────────────────────────────────────── */
  if (!authReady) {
    return (
      <div style={{ minHeight: '100dvh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg)' }}>
        <div style={{ color: 'var(--text-muted)', fontSize: '14px' }}>Loading…</div>
      </div>
    )
  }

  if (!user) {
    return <LoginPage />
  }

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
          {/* User identity */}
          <div style={styles.userChip}>
            <span style={styles.userDot} />
            {user.display_name}
          </div>

          {/* Briefings button */}
          <button
            onClick={() => setBriefingsOpen(true)}
            style={styles.briefingsBtn}
            title="Agent briefings"
          >
            Briefings
            {unseenCount > 0 && (
              <span style={styles.badge}>{unseenCount}</span>
            )}
          </button>

          {/* Logout */}
          <button onClick={handleLogout} style={styles.logoutBtn} title="Sign out">
            Sign out
          </button>
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

      {briefingsOpen && (
        <BriefingsPanel
          onClose={() => { setBriefingsOpen(false); setUnseenCount(0) }}
        />
      )}
    </div>
  )
}

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
  tagline: { fontSize: '12px', color: 'var(--text-muted)' },
  headerRight: { display: 'flex', alignItems: 'center', gap: '8px', marginLeft: 'auto' },

  userChip: {
    display: 'flex', alignItems: 'center', gap: '6px',
    fontSize: '12px', color: 'var(--text-muted)',
    background: 'var(--surface-2)', borderRadius: '20px',
    padding: '4px 10px', border: '1px solid var(--border)',
  },
  userDot: {
    width: '6px', height: '6px', borderRadius: '50%',
    background: 'var(--c-email)', flexShrink: 0,
  },

  briefingsBtn: {
    display: 'flex', alignItems: 'center', gap: '6px',
    background: 'var(--surface-2)', border: '1px solid var(--border)',
    color: 'var(--text)', borderRadius: '6px', padding: '5px 10px',
    fontSize: '12px', cursor: 'pointer', fontFamily: 'inherit',
  },
  badge: {
    background: 'var(--c-orch)', color: '#fff',
    borderRadius: '10px', padding: '1px 6px',
    fontSize: '10px', fontWeight: 700,
  },
  logoutBtn: {
    background: 'none', border: '1px solid var(--border)',
    color: 'var(--text-dim)', borderRadius: '6px', padding: '5px 10px',
    fontSize: '12px', cursor: 'pointer', fontFamily: 'inherit',
  },

  main: { display: 'flex', flex: 1, overflow: 'hidden' },
}
