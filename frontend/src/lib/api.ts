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

const API_BASE = import.meta.env.VITE_API_BASE_URL || "/api";

function getToken(): string | null {
  return localStorage.getItem("axolot_access");
}

export function setTokens(access: string, refresh: string) {
  localStorage.setItem("axolot_access", access);
  localStorage.setItem("axolot_refresh", refresh);
}

export function clearTokens() {
  localStorage.removeItem("axolot_access");
  localStorage.removeItem("axolot_refresh");
}

async function request<T>(
  path: string,
  init: RequestInit & { silent?: boolean } = {}
): Promise<T> {
  const { silent, ...fetchInit } = init;
  const token = getToken();
  const headers: Record<string, string> = {
    "Content-Type": "application/json",
    ...(fetchInit.headers as Record<string, string> | undefined),
  };
  if (token) headers["Authorization"] = `Bearer ${token}`;

  let res: Response;
  try {
    res = await fetch(`${API_BASE}${path}`, { ...fetchInit, headers });
  } catch {
    if (!silent) pushToast("Network unreachable — is the API running?");
    throw new Error("network_error");
  }

  const json: (ApiResponse<T> & { message?: string }) = await res
    .json()
    .catch(() => ({
      success: false,
      data: null,
      error: `HTTP ${res.status}`,
      meta: { timestamp: new Date().toISOString(), agent_id: null },
    }));

  if (!res.ok || !json.success) {
    // New routes use error:{code,message}; legacy routes use error:string + message.
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
    // 401 during the auth bootstrap is expected — don't shout about it.
    if (!silent && res.status !== 401) {
      pushToast(msg, "error");
    }
    throw new Error(msg);
  }
  return json.data as T;
}

export const api = {
  // auth
  googleAuth: (payload: { email: string; name: string; avatar_url?: string }) =>
    request<{
      access_token: string;
      refresh_token: string;
      user_id: string;
      onboarded: boolean;
    }>("/auth/google", { method: "POST", body: JSON.stringify(payload) }),

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
