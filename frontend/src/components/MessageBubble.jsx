export default function MessageBubble({ message }) {
  const { role, content, isError, streaming } = message

  if (role === 'system') {
    return (
      <div style={styles.system}>
        <span>{content}</span>
      </div>
    )
  }

  const isUser = role === 'user'

  return (
    <div style={{ ...styles.row, justifyContent: isUser ? 'flex-end' : 'flex-start' }}>
      {!isUser && <div style={styles.avatar}>A</div>}
      <div
        style={{
          ...styles.bubble,
          ...(isUser ? styles.userBubble : styles.assistantBubble),
          ...(isError ? styles.errorBubble : {}),
        }}
      >
        <div style={styles.content}>
          {renderContent(content)}
        </div>
        {streaming && <span style={styles.cursor} aria-hidden="true">▋</span>}
      </div>
    </div>
  )
}

/** Minimal markdown-like rendering: bold, inline code, line breaks */
function renderContent(text) {
  if (!text) return null

  const lines = text.split('\n')
  return lines.map((line, i) => (
    <span key={i}>
      {renderInline(line)}
      {i < lines.length - 1 && <br />}
    </span>
  ))
}

function renderInline(text) {
  // Handle **bold** and `code` inline
  const parts = text.split(/(\*\*[^*]+\*\*|`[^`]+`)/g)
  return parts.map((part, i) => {
    if (part.startsWith('**') && part.endsWith('**')) {
      return <strong key={i}>{part.slice(2, -2)}</strong>
    }
    if (part.startsWith('`') && part.endsWith('`')) {
      return <code key={i} style={styles.inlineCode}>{part.slice(1, -1)}</code>
    }
    return part
  })
}

const styles = {
  row: {
    display: 'flex',
    alignItems: 'flex-end',
    gap: '8px',
    padding: '2px 0',
  },
  avatar: {
    width: '28px',
    height: '28px',
    borderRadius: '50%',
    background: 'var(--c-orch)',
    color: '#fff',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    fontSize: '12px',
    fontWeight: 700,
    flexShrink: 0,
  },
  bubble: {
    maxWidth: '72%',
    padding: '10px 14px',
    borderRadius: '12px',
    lineHeight: 1.6,
    fontSize: '14px',
    wordBreak: 'break-word',
    position: 'relative',
  },
  userBubble: {
    background: 'var(--c-user)',
    color: '#fff',
    borderBottomRightRadius: '4px',
  },
  assistantBubble: {
    background: 'var(--surface-2)',
    border: '1px solid var(--border)',
    color: 'var(--text)',
    borderBottomLeftRadius: '4px',
  },
  errorBubble: {
    background: 'rgba(248,81,73,0.12)',
    border: '1px solid var(--c-error)',
    color: 'var(--c-error)',
  },
  content: {
    whiteSpace: 'pre-wrap',
  },
  inlineCode: {
    fontFamily: "'JetBrains Mono', monospace",
    fontSize: '12px',
    background: 'rgba(110,64,201,0.2)',
    padding: '1px 4px',
    borderRadius: '3px',
  },
  cursor: {
    display: 'inline-block',
    marginLeft: '2px',
    color: 'var(--c-orch)',
    animation: 'blink 1s step-end infinite',
  },
  system: {
    textAlign: 'center',
    color: 'var(--c-email)',
    fontSize: '12px',
    padding: '4px 0',
  },
}

// Inject blink keyframes once
if (typeof document !== 'undefined' && !document.getElementById('axo-blink')) {
  const style = document.createElement('style')
  style.id = 'axo-blink'
  style.textContent = '@keyframes blink { 0%,100%{opacity:1} 50%{opacity:0} }'
  document.head.appendChild(style)
}
