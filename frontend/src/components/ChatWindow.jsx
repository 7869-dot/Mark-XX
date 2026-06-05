import { useState, useRef, useEffect } from 'react'
import MessageBubble from './MessageBubble.jsx'

export default function ChatWindow({ messages, isLoading, onSend }) {
  const [input, setInput] = useState('')
  const bottomRef = useRef(null)
  const textareaRef = useRef(null)

  useEffect(() => {
    bottomRef.current?.scrollIntoView({ behavior: 'smooth' })
  }, [messages])

  function handleKeyDown(e) {
    if (e.key === 'Enter' && !e.shiftKey) {
      e.preventDefault()
      submit()
    }
  }

  function submit() {
    const text = input.trim()
    if (!text || isLoading) return
    onSend(text)
    setInput('')
    textareaRef.current?.focus()
  }

  const isEmpty = messages.length === 0

  return (
    <div style={styles.root}>
      {/* Message list */}
      <div style={styles.messages}>
        {isEmpty && !isLoading && <EmptyState />}
        {messages.map((msg) => (
          <MessageBubble key={msg.id} message={msg} />
        ))}
        {isLoading && messages[messages.length - 1]?.role !== 'assistant' && (
          <TypingIndicator />
        )}
        <div ref={bottomRef} />
      </div>

      {/* Input area */}
      <div style={styles.inputArea}>
        <textarea
          ref={textareaRef}
          value={input}
          onChange={e => setInput(e.target.value)}
          onKeyDown={handleKeyDown}
          placeholder="Ask Axolotl anything — search the web, send emails, or chain tasks…"
          disabled={isLoading}
          rows={1}
          style={styles.textarea}
        />
        <button
          onClick={submit}
          disabled={!input.trim() || isLoading}
          style={{
            ...styles.sendBtn,
            ...((!input.trim() || isLoading) ? styles.sendBtnDisabled : {}),
          }}
          aria-label="Send"
        >
          {isLoading ? <Spinner /> : <SendIcon />}
        </button>
      </div>
    </div>
  )
}

function EmptyState() {
  return (
    <div style={styles.empty}>
      <div style={styles.emptyIcon}>🦎</div>
      <div style={styles.emptyTitle}>Axolotl is ready</div>
      <div style={styles.emptyHints}>
        {[
          'Find the latest news on AI breakthroughs',
          'Email a summary of [topic] to me@example.com',
          'Research X and draft an email about it',
        ].map(h => (
          <div key={h} style={styles.hint}>{h}</div>
        ))}
      </div>
    </div>
  )
}

function TypingIndicator() {
  return (
    <div style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '4px 0' }}>
      <div style={{
        width: '28px', height: '28px', borderRadius: '50%',
        background: 'var(--c-orch)', color: '#fff',
        display: 'flex', alignItems: 'center', justifyContent: 'center',
        fontSize: '12px', fontWeight: 700, flexShrink: 0,
      }}>A</div>
      <div style={{
        background: 'var(--surface-2)', border: '1px solid var(--border)',
        borderRadius: '12px', borderBottomLeftRadius: '4px',
        padding: '12px 16px', display: 'flex', gap: '4px',
      }}>
        {[0, 1, 2].map(i => (
          <div key={i} style={{
            width: '6px', height: '6px', borderRadius: '50%',
            background: 'var(--c-orch)',
            animation: `bounce 1.2s ease-in-out ${i * 0.2}s infinite`,
          }} />
        ))}
      </div>
    </div>
  )
}

function SendIcon() {
  return (
    <svg width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
      <line x1="22" y1="2" x2="11" y2="13" />
      <polygon points="22 2 15 22 11 13 2 9 22 2" />
    </svg>
  )
}

function Spinner() {
  return (
    <div style={{
      width: '14px', height: '14px', borderRadius: '50%',
      border: '2px solid rgba(255,255,255,0.3)',
      borderTopColor: '#fff',
      animation: 'spin 0.6s linear infinite',
    }} />
  )
}

// Inject animation keyframes once
if (typeof document !== 'undefined' && !document.getElementById('axo-anim')) {
  const s = document.createElement('style')
  s.id = 'axo-anim'
  s.textContent = `
    @keyframes bounce {
      0%,80%,100%{ transform:translateY(0) }
      40%{ transform:translateY(-6px) }
    }
    @keyframes spin {
      to { transform: rotate(360deg) }
    }
  `
  document.head.appendChild(s)
}

const styles = {
  root: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    overflow: 'hidden',
    borderRight: '1px solid var(--border)',
  },
  messages: {
    flex: 1,
    overflowY: 'auto',
    padding: '20px 24px',
    display: 'flex',
    flexDirection: 'column',
    gap: '12px',
  },
  inputArea: {
    display: 'flex',
    gap: '10px',
    padding: '16px 20px',
    borderTop: '1px solid var(--border)',
    background: 'var(--surface)',
    alignItems: 'flex-end',
  },
  textarea: {
    flex: 1,
    background: 'var(--surface-2)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius)',
    color: 'var(--text)',
    padding: '10px 14px',
    fontSize: '14px',
    fontFamily: 'inherit',
    resize: 'none',
    outline: 'none',
    lineHeight: 1.5,
    maxHeight: '140px',
    overflowY: 'auto',
    transition: 'border-color 0.15s',
  },
  sendBtn: {
    width: '38px',
    height: '38px',
    borderRadius: 'var(--radius-sm)',
    border: 'none',
    background: 'var(--c-orch)',
    color: '#fff',
    cursor: 'pointer',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    flexShrink: 0,
    transition: 'opacity 0.15s',
  },
  sendBtnDisabled: {
    opacity: 0.4,
    cursor: 'not-allowed',
  },
  empty: {
    flex: 1,
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '12px',
    padding: '40px 20px',
    marginTop: '40px',
  },
  emptyIcon: { fontSize: '48px' },
  emptyTitle: {
    fontSize: '18px',
    fontWeight: 600,
    color: 'var(--text)',
  },
  emptyHints: {
    display: 'flex',
    flexDirection: 'column',
    gap: '8px',
    marginTop: '8px',
    width: '100%',
    maxWidth: '420px',
  },
  hint: {
    background: 'var(--surface-2)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius)',
    padding: '8px 14px',
    fontSize: '13px',
    color: 'var(--text-muted)',
    cursor: 'default',
  },
}
