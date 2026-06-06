/**
 * JWT-aware fetch wrapper.
 * All API calls go through apiFetch() so auth headers are always included.
 * The JWT is stored in localStorage under JWT_KEY.
 */

const JWT_KEY = 'axolotl_jwt'

export function getJwt() {
  return localStorage.getItem(JWT_KEY)
}

export function setJwt(token) {
  localStorage.setItem(JWT_KEY, token)
}

export function clearJwt() {
  localStorage.removeItem(JWT_KEY)
}

export function isAuthenticated() {
  return !!getJwt()
}

export function authHeaders(extra = {}) {
  const jwt = getJwt()
  return {
    'Content-Type': 'application/json',
    ...(jwt ? { Authorization: `Bearer ${jwt}` } : {}),
    ...extra,
  }
}

/**
 * Drop-in fetch() replacement that attaches the JWT automatically.
 * Returns the raw Response; callers should check .ok and parse .json() as needed.
 */
export async function apiFetch(path, options = {}) {
  return fetch(path, {
    ...options,
    headers: {
      ...authHeaders(),
      ...options.headers,
    },
  })
}

export async function apiGet(path) {
  return apiFetch(path)
}

export async function apiPost(path, body) {
  return apiFetch(path, {
    method: 'POST',
    body: JSON.stringify(body),
  })
}

/* ── Phase 3 endpoints ───────────────────────────────────────────────── */

export async function getBriefing() {
  const res = await apiGet('/briefing')
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function getProposedActions(status = 'pending') {
  const res = await apiGet(`/proposed-actions?status=${status}`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function approveAction(id) {
  const res = await apiPost(`/proposed-actions/${id}/approve`)
  if (!res.ok) {
    const d = await res.json().catch(() => ({}))
    throw new Error(d.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function rejectAction(id) {
  const res = await apiPost(`/proposed-actions/${id}/reject`)
  if (!res.ok) {
    const d = await res.json().catch(() => ({}))
    throw new Error(d.detail || `HTTP ${res.status}`)
  }
  return res.json()
}

export async function getNudges() {
  const res = await apiGet('/nudges')
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}

export async function dismissNudge(id) {
  const res = await apiPost(`/nudges/${id}/dismiss`)
  if (!res.ok) throw new Error(`HTTP ${res.status}`)
  return res.json()
}
