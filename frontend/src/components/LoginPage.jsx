/**
 * Full-screen login page shown when the user has no valid JWT.
 * Redirects to the backend OAuth flow on button click.
 */
export default function LoginPage({ loading }) {
  return (
    <div style={s.root}>
      <div style={s.card}>
        <div style={s.logoRow}>
          <span style={s.logoIcon}>🦎</span>
          <span style={s.logoText}>Axolotl</span>
        </div>

        <p style={s.tagline}>The next frontier of AI agents</p>

        <div style={s.divider} />

        <p style={s.body}>
          Your personal AI chief of staff. Searches the web, drafts emails,
          manages your calendar, and discovers collaborators — all while you're
          offline.
        </p>

        {loading ? (
          <div style={s.loading}>Signing in…</div>
        ) : (
          <a href="/auth/login" style={s.btnLink}>
            <button style={s.btn}>
              <GoogleIcon />
              Sign in with Google
            </button>
          </a>
        )}

        <p style={s.note}>
          Gmail &amp; Calendar access is requested so your agent can read
          emails and events. No data is shared externally.
        </p>
      </div>
    </div>
  )
}

function GoogleIcon() {
  return (
    <svg width="18" height="18" viewBox="0 0 48 48" style={{ flexShrink: 0 }}>
      <path fill="#EA4335" d="M24 9.5c3.54 0 6.71 1.22 9.21 3.6l6.85-6.85C35.9 2.38 30.47 0 24 0 14.62 0 6.51 5.38 2.56 13.22l7.98 6.19C12.43 13.72 17.74 9.5 24 9.5z"/>
      <path fill="#4285F4" d="M46.98 24.55c0-1.57-.15-3.09-.38-4.55H24v9.02h12.94c-.58 2.96-2.26 5.48-4.78 7.18l7.73 6c4.51-4.18 7.09-10.36 7.09-17.65z"/>
      <path fill="#FBBC05" d="M10.53 28.59c-.48-1.45-.76-2.99-.76-4.59s.27-3.14.76-4.59l-7.98-6.19C.92 16.46 0 20.12 0 24c0 3.88.92 7.54 2.56 10.78l7.97-6.19z"/>
      <path fill="#34A853" d="M24 48c6.48 0 11.93-2.13 15.89-5.81l-7.73-6c-2.15 1.45-4.92 2.3-8.16 2.3-6.26 0-11.57-4.22-13.47-9.91l-7.98 6.19C6.51 42.62 14.62 48 24 48z"/>
    </svg>
  )
}

const s = {
  root: {
    minHeight: '100dvh',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    background: 'var(--bg)',
    padding: '24px',
  },
  card: {
    width: '100%',
    maxWidth: '400px',
    background: 'var(--surface)',
    border: '1px solid var(--border)',
    borderRadius: '16px',
    padding: '36px 32px',
    display: 'flex',
    flexDirection: 'column',
    alignItems: 'center',
    gap: '16px',
    boxShadow: '0 20px 60px rgba(0,0,0,0.4)',
  },
  logoRow: {
    display: 'flex',
    alignItems: 'center',
    gap: '10px',
  },
  logoIcon: { fontSize: '36px' },
  logoText: {
    fontSize: '28px',
    fontWeight: 800,
    color: 'var(--c-orch)',
    letterSpacing: '-0.5px',
  },
  tagline: {
    fontSize: '13px',
    color: 'var(--text-muted)',
    margin: 0,
    textAlign: 'center',
  },
  divider: {
    width: '100%',
    height: '1px',
    background: 'var(--border)',
  },
  body: {
    fontSize: '13px',
    color: 'var(--text-muted)',
    lineHeight: 1.6,
    textAlign: 'center',
    margin: 0,
  },
  btnLink: { textDecoration: 'none', width: '100%' },
  btn: {
    width: '100%',
    display: 'flex',
    alignItems: 'center',
    justifyContent: 'center',
    gap: '10px',
    padding: '12px 20px',
    background: '#fff',
    color: '#333',
    border: 'none',
    borderRadius: '8px',
    fontSize: '14px',
    fontWeight: 600,
    cursor: 'pointer',
    fontFamily: 'inherit',
  },
  loading: {
    color: 'var(--text-muted)',
    fontSize: '13px',
    padding: '12px 0',
  },
  note: {
    fontSize: '11px',
    color: 'var(--text-dim)',
    textAlign: 'center',
    lineHeight: 1.5,
    margin: 0,
  },
}
