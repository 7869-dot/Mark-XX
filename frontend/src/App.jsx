import { useState, useRef, useCallback } from 'react'
import ChatWindow from './components/ChatWindow.jsx'
import AgentActivity from './components/AgentActivity.jsx'
import EmailConfirm from './components/EmailConfirm.jsx'

export default function App() {
  const [messages, setMessages]     = useState([])
  const [agentEvents, setAgentEvents] = useState([])
  const [emailDraft, setEmailDraft] = useState(null)   // {draft_id, to, subject, body}
  const [isLoading, setIsLoading]   = useState(false)
  const [activeAgent, setActiveAgent] = useState(null)

  // Accumulate streaming tokens without stale-closure issues
  const streamRef = useRef('')

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
        // Use a sentinel message id so we can replace the streaming bubble
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
          return final
            ? [...prev, { id: Date.now(), role: 'assistant', content: final }]
            : prev
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
        buf = lines.pop()               // keep partial last line

        for (const line of lines) {
          if (!line.startsWith('data: ')) continue
          try {
            handleEvent(JSON.parse(line.slice(6)))
          } catch { /* skip malformed */ }
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

      setMessages(prev => [
        ...prev,
        { id: Date.now(), role: 'system', content: `✓ Email sent to ${edited.to}` },
      ])
      setEmailDraft(null)
    } catch (err) {
      alert(`Failed to send email: ${err.message}`)
    }
  }, [])

  return (
    <div style={styles.root}>
      {/* Header */}
      <header style={styles.header}>
        <span style={styles.logo}>
          <span style={styles.logoIcon}>🦎</span>
          Axolotl
        </span>
        <span style={styles.tagline}>The next frontier of AI agents</span>
      </header>

      {/* Main layout */}
      <div style={styles.main}>
        <ChatWindow
          messages={messages}
          isLoading={isLoading}
          onSend={sendMessage}
        />
        <AgentActivity
          events={agentEvents}
          activeAgent={activeAgent}
        />
      </div>

      {/* Email confirmation modal */}
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
    display: 'flex',
    flexDirection: 'column',
    height: '100dvh',
    background: 'var(--bg)',
    overflow: 'hidden',
  },
  header: {
    display: 'flex',
    alignItems: 'center',
    gap: '12px',
    padding: '0 24px',
    height: '52px',
    borderBottom: '1px solid var(--border)',
    background: 'var(--surface)',
    flexShrink: 0,
  },
  logo: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    fontWeight: 700,
    fontSize: '17px',
    color: 'var(--c-orch)',
    letterSpacing: '-0.3px',
  },
  logoIcon: { fontSize: '20px' },
  tagline: {
    fontSize: '12px',
    color: 'var(--text-muted)',
    marginLeft: '4px',
  },
  main: {
    display: 'flex',
    flex: 1,
    overflow: 'hidden',
  },
}
