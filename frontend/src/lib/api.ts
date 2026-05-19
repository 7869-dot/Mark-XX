import type {
  Agent,
  AgentStats,
  ApiResponse,
  Connection,
  Discovery,
  FeedItem,
  Interaction,
  NetworkStats,
  PublicAgentProfile,
  Task,
} from "@/types";
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

// `refresh` is accepted for call-site compatibility but no longer stored —
// the refresh token now lives in an httpOnly cookie set by the backend.
export function setTokens(access: string, _refresh?: string) {
  setAccessToken(access);
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
        // Cleared on the next tick so concurrent callers share this attempt.
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
      // Refresh definitively failed — the session is dead regardless of who
      // asked. `silent` only suppresses the toast, never the auth redirect.
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

/** Shared request helper for the src/api/* modules (auth + envelope aware). */
export function apiRequest<T>(
  path: string,
  init: RequestInit & { silent?: boolean } = {}
): Promise<T> {
  return request<T>(path, init);
}

export type ChatMessage = {
  id: string;
  role: "user" | "agent";
  content: string;
  created_at: string;
};

export const api = {
  // agent
  getAgent: (silent = false) => request<Agent>("/agent/me", { silent }),
  updateAgent: (payload: Partial<{
    name: string;
    goals: string[];
    personality_vector: Record<string, number>;
    onboarded: { completed: boolean; step: number };
  }>) => request<Agent>("/agent/me", { method: "PUT", body: JSON.stringify(payload) }),
  getStats: () => request<AgentStats>("/agent/stats"),
  getFeed: (offset = 0, limit = 30) =>
    request<{ items: FeedItem[]; next_offset: number }>(
      `/agent/activity-feed?limit=${limit}&offset=${offset}`
    ),
  regenerateAvatar: () =>
    request<{ avatar_seed: string }>("/agent/regenerate-avatar", { method: "POST" }),

  // chat
  chatHistory: () =>
    request<{ messages: ChatMessage[] }>("/chat/history"),
  sendChatMessage: (message: string) =>
    request<{ reply: ChatMessage; echo: ChatMessage }>("/chat/message", {
      method: "POST",
      body: JSON.stringify({ message }),
    }),

  // tasks
  createTask: (payload: {
    title: string;
    description: string;
    task_type: string;
    priority?: number;
    requires_human_approval?: boolean;
  }) => request<Task>("/tasks/create", { method: "POST", body: JSON.stringify(payload) }),
  myTasks: () => request<Task[]>("/tasks/my"),
  pendingTasks: () => request<Task[]>("/tasks/pending"),
  getTask: (id: string) => request<Task>(`/tasks/${id}`),
  approveTask: (id: string) =>
    request<Task>(`/tasks/${id}/approve`, { method: "POST" }),
  rejectTask: (id: string, feedback?: string) =>
    request<Task>(`/tasks/${id}/reject`, {
      method: "POST",
      body: JSON.stringify({ feedback }),
    }),

  // network
  discover: (limit = 10) =>
    request<Discovery[]>(`/agents/discover?limit=${limit}`),
  connections: (connectionType?: string) =>
    request<Connection[]>(
      "/agents/connections" +
        (connectionType ? `?connection_type=${connectionType}` : "")
    ),
  interact: (payload: {
    target_agent_id: string;
    interaction_type?: string;
    custom_message?: string;
  }) =>
    request<Interaction & { compatibility_breakdown?: unknown }>(
      "/agents/interact",
      { method: "POST", body: JSON.stringify(payload) }
    ),
  interactions: (status?: string) =>
    request<Interaction[]>(
      "/agents/interactions" + (status ? `?status=${status}` : "")
    ),
  interactionsFeed: (offset = 0, limit = 20) =>
    request<{ items: Interaction[]; next_offset: number }>(
      `/agents/interactions/feed?limit=${limit}&offset=${offset}`
    ),
  acceptInteraction: (id: string) =>
    request<{ status: string; interaction_id: string }>(
      `/agents/interactions/${id}/accept`,
      { method: "POST" }
    ),
  declineInteraction: (id: string) =>
    request<{ status: string; interaction_id: string }>(
      `/agents/interactions/${id}/decline`,
      { method: "POST" }
    ),
  publicProfile: (id: string) =>
    request<PublicAgentProfile>(`/agents/${id}/profile`),
  humanFollowup: (id: string) =>
    request<{
      ok: boolean;
      other_user_name: string | null;
      other_user_email: string | null;
    }>(`/agents/interactions/${id}/human-followup`, { method: "POST" }),
  networkStats: () => request<NetworkStats>("/network/stats"),

  // memory
  memoryTimeline: () =>
    request<{
      id: string;
      memory_type: string;
      content: string;
      importance_score: number;
      created_at: string;
    }[]>("/memory/timeline"),
  personality: () =>
    request<{
      agent_personality: Record<string, number>;
      user_traits: Record<string, unknown>;
      interests: string[];
      communication_style: string;
      notes: string;
    }>("/memory/personality"),

  // platform
  platformStats: () =>
    request<{
      total_agents: number;
      tasks_completed_total: number;
      interactions_today: number;
    }>("/platform/stats"),
};
