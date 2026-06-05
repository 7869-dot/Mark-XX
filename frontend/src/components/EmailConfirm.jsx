import { useState } from 'react'

export default function EmailConfirm({ draft, onSend, onCancel }) {
  const [to, setTo]           = useState(draft.to ?? '')
  const [subject, setSubject] = useState(draft.subject ?? '')
  const [body, setBody]       = useState(draft.body ?? '')
  const [sending, setSending] = useState(false)

  async function handleSend() {
    setSending(true)
    await onSend({ draft_id: draft.draft_id, to, subject, body })
    setSending(false)
  }

  return (
    <div style={styles.overlay} onClick={e => e.target === e.currentTarget && onCancel()}>
      <div style={styles.modal}>
        {/* Header */}
        <div style={styles.modalHeader}>
          <div style={styles.modalTitle}>
            <span style={styles.emailIcon}>✉️</span>
            Review & Send Email
          </div>
          <button onClick={onCancel} style={styles.closeBtn} aria-label="Cancel">✕</button>
        </div>

        <div style={styles.notice}>
          The Email Agent has drafted this message. Review and edit before sending.
        </div>

        {/* Fields */}
        <div style={styles.field}>
          <label style={styles.label}>To</label>
          <input
            type="email"
            value={to}
            onChange={e => setTo(e.target.value)}
            style={styles.input}
            placeholder="recipient@example.com"
          />
        </div>

        <div style={styles.field}>
          <label style={styles.label}>Subject</label>
          <input
            type="text"
            value={subject}
            onChange={e => setSubject(e.target.value)}
            style={styles.input}
            placeholder="Subject"
          />
        </div>

        <div style={styles.field}>
          <label style={styles.label}>Body</label>
          <textarea
            value={body}
            onChange={e => setBody(e.target.value)}
            style={styles.bodyArea}
            rows={10}
          />
        </div>

        {/* Actions */}
        <div style={styles.actions}>
          <button onClick={onCancel} style={styles.cancelBtn} disabled={sending}>
            Discard
          </button>
          <button
            onClick={handleSend}
            style={{ ...styles.sendBtn, ...(sending ? styles.sendBtnLoading : {}) }}
            disabled={sending || !to.trim()}
          >
            {sending ? 'Sending…' : '↑ Send Email'}
          </button>
        </div>
      </div>
    </div>
  )
}

const styles = {
  overlay: {
    position: 'fixed',
    inset: 0,
    background: 'rgba(0,0,0,0.65)',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    zIndex: 100,
    padding: '20px',
  },
  modal: {
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: '14px',
    width: '100%',
    maxWidth: '560px',
    maxHeight: '90vh',
    overflowY: 'auto',
    padding: '24px',
    display: 'flex',
    flexDirection: 'column',
    gap: '16px',
    boxShadow: '0 24px 64px rgba(0,0,0,0.5)',
  },
  modalHeader: {
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'space-between',
  },
  modalTitle: {
    display: 'flex',
    alignItems: 'center',
    gap: '8px',
    fontWeight: 700,
    fontSize: '16px',
    color: 'var(--text)',
  },
  emailIcon: { fontSize: '18px' },
  closeBtn: {
    background: 'none',
    border: 'none',
    color: 'var(--text-muted)',
    cursor: 'pointer',
    fontSize: '16px',
    padding: '4px',
    borderRadius: '4px',
    lineHeight: 1,
  },
  notice: {
    background: 'rgba(63,185,80,0.08)',
    border: '1px solid rgba(63,185,80,0.25)',
    borderRadius: 'var(--radius-sm)',
    padding: '8px 12px',
    fontSize: '12px',
    color: 'var(--c-email)',
  },
  field: {
    display: 'flex',
    flexDirection: 'column',
    gap: '6px',
  },
  label: {
    fontSize: '12px',
    fontWeight: 600,
    color: 'var(--text-muted)',
    textTransform: 'uppercase',
    letterSpacing: '0.05em',
  },
  input: {
    background: 'var(--surface-2)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm)',
    color: 'var(--text)',
    padding: '9px 12px',
    fontSize: '14px',
    fontFamily: 'inherit',
    outline: 'none',
    width: '100%',
  },
  bodyArea: {
    background: 'var(--surface-2)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm)',
    color: 'var(--text)',
    padding: '9px 12px',
    fontSize: '13px',
    fontFamily: "'JetBrains Mono', monospace",
    outline: 'none',
    resize: 'vertical',
    lineHeight: 1.6,
    width: '100%',
  },
  actions: {
    display: 'flex',
    justifyContent: 'flex-end',
    gap: '10px',
    paddingTop: '4px',
  },
  cancelBtn: {
    background: 'var(--surface-2)',
    border: '1px solid var(--border)',
    borderRadius: 'var(--radius-sm)',
    color: 'var(--text-muted)',
    padding: '8px 16px',
    fontSize: '14px',
    cursor: 'pointer',
    fontFamily: 'inherit',
  },
  sendBtn: {
    background: 'var(--c-email)',
    border: 'none',
    borderRadius: 'var(--radius-sm)',
    color: '#fff',
    padding: '8px 20px',
    fontSize: '14px',
    fontWeight: 600,
    cursor: 'pointer',
    fontFamily: 'inherit',
    transition: 'opacity 0.15s',
  },
  sendBtnLoading: {
    opacity: 0.6,
    cursor: 'not-allowed',
  },
}
