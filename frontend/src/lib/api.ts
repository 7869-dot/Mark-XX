import type { ApiResponse, User } from "@/types";
import { pushToast } from "@/lib/toast";

// Vercel sets VITE_BACKEND_URL; local dev falls back to the Vite /api proxy.
const API_BASE =
  import.meta.env.VITE_BACKEND_URL ||
  import.meta.env.VITE_API_BASE_URL ||
  "/api";

const TOKEN_KEY = "axolot_token";

function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

export function setAccessToken(access: string) {
  localStorage.setItem(TOKEN_KEY, access);
}

export function clearTokens() {
  localStorage.removeItem(TOKEN_KEY);
}

/**
 * Synchronously pull ?token=<jwt> out of the URL (set by the backend OAuth
 * redirect), persist it, and scrub it from the address bar. Runs before route
 * guards read localStorage so a fresh login isn't bounced back to "/".
 */
export function captureTokenFromUrl() {
  try {
    const url = new URL(window.location.href);
    const token = url.searchParams.get("token");
    if (token) {
      setAccessToken(token);
      url.searchParams.delete("token");
      window.history.replaceState(
        {},
        "",
        url.pathname + (url.search ? url.search : "") + url.hash
      );
    }
  } catch {
    /* non-browser / malformed URL — nothing to capture */
  }
}

let refreshInFlight: Promise<string | null> | null = null;

async function refreshAccessToken(): Promise<string | null> {
  if (!refreshInFlight) {
    refreshInFlight = (async () => {
      try {
        const res = await fetch(`${API_BASE}/auth/refresh`, {
          method: "POST",
          credentials: "include",
          headers: { "Content-Type": "application/json" },
        });
        if (!res.ok) return null;
        const json = await res.json().catch(() => null);
        const access = json?.data?.access_token as string | undefined;
        if (!access) return null;
        setAccessToken(access);
        return access;
      } catch {
        return null;
      } finally {
        setTimeout(() => {
          refreshInFlight = null;
        }, 0);
      }
    })();
  }
  return refreshInFlight;
}

function forceLogin() {
  clearTokens();
  if (window.location.pathname !== "/") window.location.href = "/";
}

async function rawRequest(
  path: string,
  fetchInit: RequestInit,
  token: string | null
): Promise<Response> {
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(fetchInit.headers as Record<string, string> | undefined),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;
  return fetch(`${API_BASE}${path}`, {
    ...fetchInit,
    headers,
    credentials: "include",
  });
}

async function request<T>(
  path: string,
  init: RequestInit & { silent?: boolean } = {}
): Promise<T> {
  const { silent, ...fetchInit } = init;
  // If another request already kicked off a token refresh, wait for it so this
  // request sends with the fresh token instead of racing it into a 401. This
  // collapses the initial page-load burst into a single refresh cycle.
  if (refreshInFlight && !path.startsWith("/auth/")) {
    await refreshInFlight;
  }
  let res: Response;
  try {
    res = await rawRequest(path, fetchInit, getToken());
  } catch {
    if (!silent) pushToast("Network unreachable — is the API running?");
    throw new Error("network_error");
  }

  // 401 → try one silent token refresh, then replay the original request once.
  if (res.status === 401 && !path.startsWith("/auth/")) {
    const fresh = await refreshAccessToken();
    if (fresh) {
      try {
        res = await rawRequest(path, fetchInit, fresh);
      } catch {
        if (!silent) pushToast("Network unreachable — is the API running?");
        throw new Error("network_error");
      }
    }
    if (res.status === 401) {
      forceLogin();
      throw new Error("unauthorized");
    }
  }

  const json: ApiResponse<T> & { message?: string } = await res
    .json()
    .catch(() => ({
      success: false,
      data: null,
      error: `HTTP ${res.status}`,
      meta: { timestamp: new Date().toISOString(), agent_id: null },
    }));

  if (!res.ok || !json.success) {
    const errAny = json.error as unknown;
    const structured =
      errAny && typeof errAny === "object"
        ? (errAny as { message?: string }).message
        : undefined;
    const msg =
      structured ||
      json.message ||
      (typeof errAny === "string" ? errAny : "") ||
      `Request failed: ${res.status}`;
    if (!silent && res.status !== 401) {
      pushToast(msg, "error");
    }
    throw new Error(msg);
  }
  return json.data as T;
}

// ── PA-core domain types ─────────────────────────────────────────────────────
export type OnboardingQuestion = {
  id: string;
  type: "options" | "text";
  question: string;
  options?: string[];
  multi?: boolean;
};

export type WebFind = {
  id: string;
  title: string;
  url: string;
  summary: string;
  category: string;
  relevance_score: number;
};

export type SubAgentName = "email_agent" | "web_agent";

export type SubAgentStatus = {
  agent_name: SubAgentName | string;
  last_run: string | null;
  last_summary: string | null;
  status: string;
};

/** Session / briefing payload — onboarding gate OR the full morning briefing.
 *  /jarvis/session/start and GET /jarvis/briefing return the same shape. */
export type JarvisSession =
  | { onboarding: true; greeting: string; questions: OnboardingQuestion[] }
  | {
      onboarding: false;
      greeting: string;
      briefing: string;
      action_items: string[];
      reports: {
        email: Record<string, any>;
        web: { top_finds?: WebFind[] } & Record<string, any>;
      };
      agent_status: SubAgentStatus[];
      focus_prompt: string;
    };

export type ChatModeValue = "auto" | "default" | "email" | "schedule" | "research" | "post";

export type JarvisAction = {
  type: "draft_email" | "schedule_event" | "research_result" | "post_draft";
  payload: Record<string, any>;
  requires_approval: boolean;
};

export type JarvisChatResponse = {
  reply: string;
  mode: ChatModeValue;
  action: JarvisAction | null;
  follow_up: string | null;
  // When mode=auto, the sub-agent Jarvis delegated to (web | email | … | self).
  delegated_to?: string | null;
  remembered_interests?: string[];
};

export type EmailItem = { subject: string; from: string; suggested_reply?: string };

export type EmailReport = {
  connected: boolean;
  urgent: EmailItem[];
  important: EmailItem[];
  low: EmailItem[];
  action_required: EmailItem[];
  counts: { urgent: number; important: number; low: number };
};

export type IntegrationsStatus = {
  gmail: boolean;
  calendar: boolean;
  google: { connected: boolean; reason: string | null };
};

/** Approval-gated agent draft (email). GET /agents/drafts. */
export type AgentDraft = {
  id: string;
  task_id: string | null;
  agent_role: string;
  subject_line: string;
  recipient_hint: string;
  draft_content: string;
  requires_approval: boolean;
  approved: boolean | null;
  created_at: string | null;
};

export const api = {
  // identity
  getMe: (silent = false) => request<User>("/users/me", { silent }),

  // Jarvis session + chat
  jarvisSessionStart: () =>
    request<JarvisSession>("/jarvis/session/start", { method: "POST" }),
  jarvisBriefing: () => request<JarvisSession>("/jarvis/briefing"),
  jarvisChat: (
    message: string,
    mode: ChatModeValue = "auto", // Jarvis classifies + delegates to a sub-agent
    context?: Record<string, unknown>
  ) =>
    request<JarvisChatResponse>("/jarvis/chat", {
      method: "POST",
      body: JSON.stringify({ message, mode, context }),
    }),
  submitOnboarding: (answers: Record<string, unknown>) =>
    request<unknown>("/jarvis/memory", {
      method: "PATCH",
      body: JSON.stringify({ answers }),
    }),

  // agent work surfaces
  agentDrafts: () => request<{ items: AgentDraft[] }>("/agents/drafts"),
  decideDraft: (id: string, approved: boolean, content?: string) =>
    request<{ id: string; approved: boolean; sent: boolean }>(
      `/agents/drafts/${id}`,
      { method: "PATCH", body: JSON.stringify({ approved, content }) }
    ),
  agentsStatus: () => request<{ agents: SubAgentStatus[] }>("/agents/status"),
  webFindings: () =>
    request<{ items: WebFind[]; categories: string[] }>("/web/findings"),

  // Gmail / Google integration
  integrationsStatus: () => request<IntegrationsStatus>("/integrations/status"),
  gmailConnect: () =>
    request<{ authorization_url: string }>("/integrations/gmail/connect", { method: "POST" }),
  emailSummary: () => request<EmailReport>("/email/summary"),
};

/** EventSource URL for the live web-findings stream. The token rides in the
 *  query string because EventSource can't set an Authorization header. */
export function webStreamUrl(): string {
  const t = getToken() || "";
  return `${API_BASE}/web/stream?token=${encodeURIComponent(t)}`;
}
