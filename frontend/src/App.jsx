import { useState, useRef, useCallback, useEffect } from 'react'
import { AnimatePresence, motion } from 'framer-motion'
import ChatWindow from './components/ChatWindow.jsx'
import AgentActivity from './components/AgentActivity.jsx'
import EmailConfirm from './components/EmailConfirm.jsx'
import LoginPage from './components/LoginPage.jsx'
import BriefingCard from './components/BriefingCard.jsx'
import NudgeFeed from './components/NudgeFeed.jsx'
import SubAgentTabs from './components/SubAgentTabs.jsx'
import {
  getJwt, setJwt, clearJwt, isAuthenticated, authHeaders, apiFetch,
  getBriefing, getProposedActions, approveAction, rejectAction,
  getNudges, dismissNudge,
} from './api.js'

export default function App() {
  /* ── Auth ────────────────────────────────────────────────────────────── */
  const [authReady, setAuthReady] = useState(false)
  const [user, setUser]           = useState(null)

  /* ── Chat ────────────────────────────────────────────────────────────── */
  const [messages, setMessages]     = useState([])
  const [agentEvents, setAgentEvents] = useState([])
  const [emailDraft, setEmailDraft] = useState(null)
  const [isLoading, setIsLoading]   = useState(false)
  const [activeAgent, setActiveAgent] = useState(null)
  const streamRef = useRef('')

  /* ── Briefing ────────────────────────────────────────────────────────── */
  const [briefing, setBriefing]             = useState(null)
  const [briefingDismissed, setBriefingDismissed] = useState(false)

  /* ── Proposed actions ────────────────────────────────────────────────── */
  const [proposedActions, setProposedActions] = useState([])

  /* ── Nudges ──────────────────────────────────────────────────────────── */
  const [nudges, setNudges] = useState([])

  /* ── 1. Boot: harvest token, fetch user ──────────────────────────────── */
  useEffect(() => {
    const params   = new URLSearchParams(window.location.search)
    const urlToken = params.get('token')
    if (urlToken) {
      setJwt(urlToken)
      window.history.replaceState({}, '', window.location.pathname)
    }
    if (isAuthenticated()) fetchMe()
    else setAuthReady(true)
  }, [])

  async function fetchMe() {
    try {
      const res = await apiFetch('/auth/me')
      if (res.ok) {
        const u = await res.json()
        setUser(u)
        loadOnLogin()
      } else {
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
    setBriefing(null)
    setProposedActions([])
    setNudges([])
  }

  /* ── 2. On-login data load ───────────────────────────────────────────── */
  async function loadOnLogin() {
    // Run in parallel; failures are silent — each is best-effort
    await Promise.allSettled([
      loadBriefing(),
      loadProposedActions(),
      loadNudges(),
    ])
  }

  async function loadBriefing() {
    try {
      const data = await getBriefing()
      setBriefing(data)
      // Briefing may include pre-drafted proposed_actions
      if (data.proposed_actions?.length) {
        setProposedActions(prev => {
          const existing = new Set(prev.map(a => a.id))
          const fresh    = data.proposed_actions.filter(a => !existing.has(a.id))
          return [...fresh, ...prev]
        })
      }
    } catch (e) {
      console.warn('Briefing load failed:', e.message)
    }
  }

  async function loadProposedActions() {
    try {
      const data = await getProposedActions()
      setProposedActions(data)
    } catch (e) {
      console.warn('Proposed actions load failed:', e.message)
    }
  }

  async function loadNudges() {
    try {
      const data = await getNudges()
      setNudges(data)
    } catch (e) {
      console.warn('Nudges load failed:', e.message)
    }
  }

  /* ── 3. Periodic nudge polling ───────────────────────────────────────── */
  useEffect(() => {
    if (!user) return
    const id = setInterval(loadNudges, 60_000)
    return () => clearInterval(id)
  }, [user])

  /* ── 4. Proposed-action approve / reject ─────────────────────────────── */
  const handleApproveAction = useCallback(async (id, editedPayload) => {
    // For email_reply the caller may pass an edited payload
    if (editedPayload) {
      // Patch the local state so the card shows the edited content
      setProposedActions(prev =>
        prev.map(a => a.id === id ? { ...a, payload: { ...a.payload, ...editedPayload } } : a)
      )
    }
    await approveAction(id)
    // Mark approved locally
    setProposedActions(prev =>
      prev.map(a => a.id === id ? { ...a, status: 'approved' } : a)
    )
  }, [])

  const handleRejectAction = useCallback(async (id) => {
    await rejectAction(id)
    setProposedActions(prev =>
      prev.map(a => a.id === id ? { ...a, status: 'rejected' } : a)
    )
  }, [])

  /* ── 5. Nudge dismiss ────────────────────────────────────────────────── */
  const handleDismissNudge = useCallback(async (id) => {
    try {
      await dismissNudge(id)
      setNudges(prev => prev.filter(n => n.id !== id))
    } catch (e) {
      console.warn('Dismiss nudge failed:', e.message)
    }
  }, [])

  /* ── 6. Chat / SSE ───────────────────────────────────────────────────── */
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
      case 'proposed_action_created': {
        const action = { ...event.action, status: 'pending', created_at: new Date().toISOString() }
        setProposedActions(prev => {
          if (prev.some(a => a.id === action.id)) return prev
          return [action, ...prev]
        })
        break
      }
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
        method:  'POST',
        headers: authHeaders(),
        body:    JSON.stringify({ message: text }),
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)

      const reader  = res.body.getReader()
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
      const res  = await fetch('/confirm-email', {
        method:  'POST',
        headers: authHeaders(),
        body:    JSON.stringify(edited),
      })
      const data = await res.json()
      if (!res.ok) throw new Error(data.detail || 'Send failed')
      setMessages(prev => [...prev, { id: Date.now(), role: 'system', content: `Email sent to ${edited.to}` }])
      setEmailDraft(null)
    } catch (err) {
      alert(`Failed to send email: ${err.message}`)
    }
  }, [])

  /* ── Render gates ────────────────────────────────────────────────────── */
  if (!authReady) {
    return (
      <div style={{ minHeight: '100dvh', display: 'flex', alignItems: 'center', justifyContent: 'center', background: 'var(--bg)' }}>
        <div style={{ color: 'var(--text-muted)', fontSize: '14px' }}>Loading…</div>
      </div>
    )
  }
  if (!user) return <LoginPage />

  const undismissedNudges   = nudges.filter(n => !n.dismissed)
  const showBriefing        = briefing && !briefingDismissed

  /* ── Main layout ─────────────────────────────────────────────────────── */
  return (
    <div style={styles.root}>
      {/* ── Header ──────────────────────────────────────────────────────── */}
      <header style={styles.header}>
        <span style={styles.logo}>
          <span style={styles.logoIcon}>🦎</span>
          Jarvis
        </span>
        <span style={styles.tagline}>chief of staff</span>

        <div style={styles.headerRight}>
          <div style={styles.userChip}>
            <span style={styles.userDot} />
            {user.display_name}
          </div>
          {proposedActions.filter(a => a.status === 'pending').length > 0 && (
            <div style={styles.approvalChip}>
              <span style={styles.approvalPip} />
              {proposedActions.filter(a => a.status === 'pending').length} pending
            </div>
          )}
          <button onClick={handleLogout} style={styles.logoutBtn}>Sign out</button>
        </div>
      </header>

      {/* ── Two-column body ─────────────────────────────────────────────── */}
      <div style={styles.body}>
        {/* LEFT — Jarvis hub */}
        <div style={styles.leftCol}>
          <AnimatePresence>
            {showBriefing && (
              <BriefingCard
                briefing={briefing}
                onDismiss={() => setBriefingDismissed(true)}
              />
            )}
          </AnimatePresence>

          <div style={styles.chatWrap}>
            <ChatWindow messages={messages} isLoading={isLoading} onSend={sendMessage} />
          </div>

          <NudgeFeed nudges={undismissedNudges} onDismiss={handleDismissNudge} />
        </div>

        {/* RIGHT — sub-agent panels + approval surface */}
        <div style={styles.rightCol}>
          <SubAgentTabs
            agentEvents={agentEvents}
            proposedActions={proposedActions}
            onApprove={handleApproveAction}
            onReject={handleRejectAction}
          />
        </div>
      </div>

      {/* ── Legacy email confirm modal ───────────────────────────────────── */}
      {emailDraft && (
        <EmailConfirm
          draft={emailDraft}
          onSend={handleEmailSend}
          onCancel={() => setEmailDraft(null)}
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
  tagline: { fontSize: '11px', color: 'var(--text-dim)', letterSpacing: '0.04em' },
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
  approvalChip: {
    display: 'flex', alignItems: 'center', gap: '5px',
    fontSize: '11px', color: 'var(--c-approval)',
    background: 'rgba(236,72,153,0.1)',
    border: '1px solid rgba(236,72,153,0.3)',
    borderRadius: '20px', padding: '3px 10px',
  },
  approvalPip: {
    width: '5px', height: '5px', borderRadius: '50%',
    background: 'var(--c-approval)', flexShrink: 0,
    animation: 'pulse 1.5s ease-in-out infinite',
  },
  logoutBtn: {
    background: 'none', border: '1px solid var(--border)',
    color: 'var(--text-dim)', borderRadius: '6px', padding: '5px 10px',
    fontSize: '12px', cursor: 'pointer', fontFamily: 'inherit',
  },
  body: {
    display: 'flex', flex: 1, overflow: 'hidden',
  },
  leftCol: {
    flex: 1,
    minWidth: 0,
    display: 'flex',
    flexDirection: 'column',
    borderRight: '1px solid var(--border)',
    overflow: 'hidden',
  },
  chatWrap: {
    flex: 1,
    minHeight: 0,
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  },
  rightCol: {
    width: '480px',
    flexShrink: 0,
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
  },
}
