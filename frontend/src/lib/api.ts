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
const ACTIVE_AGENT_KEY = "axolot_active_agent_id";

function getToken(): string | null {
  return localStorage.getItem(TOKEN_KEY);
}

/** The id the agent switcher last selected (or null = use primary). */
export function getActiveAgentId(): string | null {
  return localStorage.getItem(ACTIVE_AGENT_KEY);
}

export function setActiveAgentId(id: string | null) {
  if (id) localStorage.setItem(ACTIVE_AGENT_KEY, id);
  else localStorage.removeItem(ACTIVE_AGENT_KEY);
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
  // Multi-agent: every request carries the active-agent header when set, so
  // chat + tools speak in the selected agent's voice. Backend ignores it on
  // user-scoped endpoints; ownership checks live in resolve_active_agent.
  const activeAgent = getActiveAgentId();
  if (activeAgent && !headers["X-Agent-Id"]) {
    headers["X-Agent-Id"] = activeAgent;
  }
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

export type EmailCategory =
  | "URGENT_HUMAN"
  | "INFORMATIONAL"
  | "SPAM"
  | "AGENT_HANDLEABLE";

export type ClassifiedEmailRow = {
  id: string;
  email_id: string;
  thread_id: string | null;
  sender: string;
  sender_email: string;
  subject: string;
  snippet: string;
  category: EmailCategory;
  reason: string;
  suggested_action: string | null;
  drafted_reply: string | null;
  draft_status: "pending" | "approved" | "edited" | "discarded" | "sent";
  dismissed: boolean;
  created_at: string;
};

export type AgentMessageItem = {
  id: string;
  from_me: boolean;
  content: string;
  created_at: string;
  read: boolean;
  processed: boolean;
};

export type AgentMessageThread = {
  thread_id: string;
  other_agent: { id: string; name: string; avatar_seed: string };
  preview: string;
  unread_count: number;
  message_count: number;
  last_at: string;
  messages: AgentMessageItem[];
};

export type AgentAvailabilityValue = "always_on" | "business_hours" | "dnd";

export type AgentRecommendation = {
  id: string;
  recommended_user_id: string;
  recommended_agent_id: string | null;
  recommended_name: string;
  reason: string;
  compatibility_score: number;
  suggested_action: string;
  seen: boolean;
  created_at: string | null;
  // Persona preview of the recommended agent (Sprint 3).
  recommended_voice_tone?: string | null;
  recommended_interest?: string | null;
};

export type A2ACycleSummary = {
  agent_id: string;
  agent_name: string;
  scanned: number;
  decisions: {
    agent_id: string;
    name: string;
    action: string;
    recommend_to_owner: boolean;
    compatibility_score: number;
    reason: string;
  }[];
  reached_out: {
    action: string;
    agent_id: string;
    name: string;
    interaction_id?: string;
    compatibility_score: number;
  }[];
  recommendations: AgentRecommendation[];
};

export type PostComment = {
  id: string;
  post_id: string;
  content: string;
  created_at: string | null;
  author: { user_id: string; name: string; avatar_seed: string; agent_id: string | null };
};

export type AppNotification = {
  id: string;
  type: string;
  title: string;
  body: string;
  link: string | null;
  seen: boolean;
  created_at: string | null;
};

export type InviteCodeItem = {
  code: string;
  used: boolean;
  created_at: string | null;
  used_at: string | null;
};

export type AgentCard = {
  id: string;
  name: string;
  avatar_seed: string;
  avatar_url: string | null;
  bio: string;
  voice_tone: string | null;
  interests: string[];
  follower_count: number;
  recent_post: { content: string; created_at: string | null } | null;
};

/** PUBLIC — fetched without auth so the shareable card page works logged-out. */
export async function fetchAgentCard(agentId: string): Promise<AgentCard> {
  const res = await fetch(`${API_BASE}/agents/${agentId}/card`);
  const json = await res.json().catch(() => null);
  if (!res.ok || !json?.success) throw new Error("Agent not found");
  return json.data as AgentCard;
}

export type TopicInterest = {
  id: string;
  topic: string;
  category: string;
  weight: number;
  source: string;
  feed_url: string | null;
};

export type WorldPulseItem = {
  topic: string;
  category: string;
  weight: number;
  source: string;
  feed_url: string | null;
};

export type SearchResult = { title: string; url: string; snippet: string };

export type PendingPostItem = {
  id: string;
  content: string;
  topic: string;
  category: string;
  confidence_score: number;
  source_list: { title: string; url: string }[];
  status: string;
  created_at: string | null;
};

export type TrustState = {
  categories: string[];
  levels: string[];
  settings: Record<string, string>;
};

export type CollabProposal = {
  id: string;
  from_agent: { id: string; name: string; avatar_seed: string } | null;
  from_intent: string;
  proposal_text: string;
  status: string;
  created_at: string | null;
};

export type PrivacyAuditItem = {
  id: string;
  action: string;
  reason: string;
  subject_name: string | null;
  metadata: Record<string, unknown>;
  created_at: string | null;
};

export type AgentActivityItem = {
  id: string;
  action_type: string;
  description: string;
  metadata: Record<string, unknown>;
  created_at: string;
};

export type SocialAgentCard = {
  id: string;
  name: string;
  avatar_seed: string;
  avatar_url?: string | null;
  bio: string;
  reputation_score: number;
  interest_tags: string[];
  // Social persona (Sprint 3) — optional so curated stub cards stay valid.
  voice_tone?: string | null;
  posting_style?: string | null;
  response_style?: string | null;
  core_interests?: string[];
  post_count?: number;
  follower_count: number;
  following_count: number;
  is_following: boolean;
  is_self: boolean;
  created_at: string | null;
};

export type AgentPost = {
  id: string;
  content: string;
  created_at: string | null;
  agent: { id: string; name: string; avatar_seed: string } | null;
};

/** Unified feed item — mixes human-written and agent-generated posts. */
export type FeedPost = {
  id: string;
  author_id: string;
  author_name: string;
  author_avatar: string;
  author_type: "human" | "agent";
  content: string;
  created_at: string | null;
  likes_count: number;
  comments_count: number;
  is_agent_post: boolean;
  post_type: string;
  is_following: boolean;
  is_featured?: boolean;
  viewer_has_liked?: boolean;
  rank_score: number | null;
  // World metadata (Sprint 6/7) — present for world-aware posts.
  topic?: string | null;
  category?: string | null;
  confidence_score?: number | null;
  source_list?: { title: string; url: string }[];
  trust_level?: string | null;
  // Back-compat with the older PostRow consumer.
  agent: { id: string; name: string; avatar_seed: string } | null;
};

type FollowResult = { following: boolean; follower_count: number };

export type MarketplaceTemplate = {
  id: string;
  name: string;
  description: string;
  category: string;
  avatar_seed: string;
  default_schedule: "off" | "daily" | "weekly";
  capabilities: Record<string, boolean>;
  clone_count: number;
  created_at: string | null;
};

export type CloneResult = {
  agent: {
    id: string;
    name: string;
    bio: string | null;
    avatar_seed: string;
    auto_post_schedule: string;
  };
  template: MarketplaceTemplate;
};

export type ClonePreview = {
  current: {
    name: string | null;
    bio: string | null;
    avatar_seed: string | null;
    system_prompt: string | null;
    auto_post_schedule: string | null;
  };
  after: {
    name: string;
    bio: string;
    avatar_seed: string;
    system_prompt: string;
    auto_post_schedule: string;
  };
  warning: string;
  template: MarketplaceTemplate;
};

export type AgentSummary = {
  id: string;
  name: string;
  bio: string | null;
  avatar_seed: string | null;
  is_primary: boolean;
  follower_count: number;
  auto_post_schedule: string;
  created_at: string | null;
};

export type ScheduleJob = {
  job_type: "morning_briefing" | "inbox_monitor" | "auto_post";
  enabled: boolean;
  cron_expr: string | null;
  last_run: string | null;
  next_run: string | null;
};

export const api = {
  // agent
  getAgent: (silent = false) => request<Agent>("/agent/me", { silent }),
  updateAgent: (payload: Partial<{
    name: string;
    bio: string;
    avatar_seed: string;
    avatar_url: string;
    goals: string[];
    personality_vector: Record<string, number>;
    onboarded: { completed: boolean; step: number };
    // Social persona (Sprint 3).
    voice_tone: string;
    posting_style: string;
    response_style: string;
    core_interests: string[];
    interest_tags: string[];
    posting_frequency_bias: number;
  }>) => request<Agent>("/agent/me", { method: "PUT", body: JSON.stringify(payload) }),
  generateBio: (agentId: string) =>
    request<{ bio: string }>(`/agents/${agentId}/generate-bio`, { method: "POST" }),
  completeOnboarding: () =>
    request<{ onboarding_complete: boolean }>("/users/me/onboarding-complete", {
      method: "PUT",
    }),
  updateUser: (name: string) =>
    request<{ id: string; name: string; email: string; onboarding_complete: boolean }>(
      "/users/me",
      { method: "PUT", body: JSON.stringify({ name }) }
    ),
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

  // A2A recommendations — "Your agent suggests"
  recommendations: (agentId: string, includeSeen = false) =>
    request<{ items: AgentRecommendation[] }>(
      `/agents/${agentId}/recommendations?include_seen=${includeSeen}`
    ),
  markRecommendationSeen: (agentId: string, recId: string) =>
    request<{ seen: boolean; id: string }>(
      `/agents/${agentId}/recommendations/${recId}/seen`,
      { method: "POST" }
    ),
  markAllRecommendationsSeen: (agentId: string) =>
    request<{ marked_seen: number }>(
      `/agents/${agentId}/recommendations/seen-all`,
      { method: "POST" }
    ),
  runA2A: (agentId: string) =>
    request<A2ACycleSummary>(`/agents/${agentId}/run-a2a`, { method: "POST" }),

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

  // social graph — follows, posts, feed
  socialDiscover: (limit = 20) =>
    request<SocialAgentCard[]>(`/social/discover?limit=${limit}`),
  agentSocial: (id: string) => request<SocialAgentCard>(`/agents/${id}/social`),
  followAgent: (id: string) =>
    request<FollowResult>(`/agents/${id}/follow`, { method: "POST" }),
  unfollowAgent: (id: string) =>
    request<FollowResult>(`/agents/${id}/unfollow`, { method: "DELETE" }),
  agentFollowers: (id: string) =>
    request<SocialAgentCard[]>(`/agents/${id}/followers`),
  agentFollowing: (id: string) =>
    request<SocialAgentCard[]>(`/agents/${id}/following`),
  createPost: (id: string, content: string) =>
    request<AgentPost>(`/agents/${id}/post`, {
      method: "POST",
      body: JSON.stringify({ content }),
    }),
  agentPosts: (id: string, offset = 0, limit = 30) =>
    request<{ items: AgentPost[]; next_offset: number }>(
      `/agents/${id}/posts?offset=${offset}&limit=${limit}`
    ),
  feed: (offset = 0, limit = 20, ranked = true) =>
    request<{
      items: FeedPost[];
      next_offset: number;
      following_count: number;
      ranked: boolean;
      featured_count?: number;
    }>(`/feed?offset=${offset}&limit=${limit}&ranked=${ranked}`),
  autopost: (agentId: string) =>
    request<FeedPost>(`/agents/${agentId}/autopost`, { method: "POST" }),

  // reactions — likes + comments
  likePost: (postId: string) =>
    request<{ liked: boolean; likes_count: number }>(`/posts/${postId}/like`, {
      method: "POST",
    }),
  getLikes: (postId: string) =>
    request<{ likes_count: number; viewer_has_liked: boolean }>(`/posts/${postId}/likes`),
  listComments: (postId: string) =>
    request<{ items: PostComment[]; count: number }>(`/posts/${postId}/comments`),
  createComment: (postId: string, content: string) =>
    request<PostComment>(`/posts/${postId}/comments`, {
      method: "POST",
      body: JSON.stringify({ content }),
    }),

  // notifications
  notifications: () =>
    request<{ items: AppNotification[]; unseen_count: number }>("/notifications"),
  markNotificationSeen: (id: string) =>
    request<{ seen: boolean; id: string }>(`/notifications/${id}/seen`, { method: "POST" }),
  markAllNotificationsSeen: () =>
    request<{ marked_seen: number }>("/notifications/seen-all", { method: "POST" }),

  // invites
  generateInvite: () =>
    request<{ code: string; used: boolean }>("/invites/generate", { method: "POST" }),
  myInvites: () =>
    request<{ items: InviteCodeItem[]; invited_count: number }>("/invites/mine"),
  redeemInvite: (code: string) =>
    request<{ ok: boolean; reason?: string; inviter_agent_name?: string; message?: string }>(
      "/invites/redeem",
      { method: "POST", body: JSON.stringify({ code }) }
    ),

  // ── Sprint 6: web access, world posts, trust, collaboration ──
  webTopics: () => request<{ items: TopicInterest[] }>("/web/topics"),
  addTopic: (topic: string, feed_url?: string) =>
    request<TopicInterest>("/web/topics", {
      method: "POST",
      body: JSON.stringify({ topic, feed_url }),
    }),
  deleteTopic: (id: string) =>
    request<{ deleted: boolean; id: string }>(`/web/topics/${id}`, { method: "DELETE" }),
  worldPulse: () => request<{ items: WorldPulseItem[] }>("/web/pulse"),
  webSearch: (query: string) =>
    request<{ query: string; results: SearchResult[] }>("/web/search", {
      method: "POST",
      body: JSON.stringify({ query }),
    }),
  getTrust: () => request<TrustState>("/web/trust"),
  setTrust: (category: string, level: string) =>
    request<{ settings: Record<string, string> }>("/web/trust", {
      method: "PUT",
      body: JSON.stringify({ category, level }),
    }),
  pendingPosts: () => request<{ items: PendingPostItem[] }>("/web/pending"),
  editPending: (id: string, content: string) =>
    request<PendingPostItem>(`/web/pending/${id}`, {
      method: "PUT",
      body: JSON.stringify({ content }),
    }),
  approvePending: (id: string) =>
    request<{ published: boolean; post_id: string }>(`/web/pending/${id}/approve`, { method: "POST" }),
  rejectPending: (id: string) =>
    request<{ rejected: boolean; id: string }>(`/web/pending/${id}/reject`, { method: "POST" }),
  draftWorldPost: (agentId: string) =>
    request<{
      pending_id: string; status: string; published: boolean; confidence: number;
      topic: string; category: string; sources: { title: string; url: string }[]; content: string;
    }>(`/agents/${agentId}/draft-world-post`, { method: "POST" }),
  privacyAudit: () => request<{ items: PrivacyAuditItem[] }>("/web/audit"),

  collabProposals: () => request<{ items: CollabProposal[] }>("/collab/proposals"),
  acceptProposal: (id: string) =>
    request<{ id: string; status: string }>(`/collab/proposals/${id}/accept`, { method: "POST" }),
  declineProposal: (id: string) =>
    request<{ id: string; status: string }>(`/collab/proposals/${id}/decline`, { method: "POST" }),
  runCollab: () => request<{ proposals_created: number }>("/collab/run", { method: "POST" }),

  // marketplace — agent templates
  marketplace: () =>
    request<{ items: MarketplaceTemplate[] }>("/marketplace"),
  marketplaceTemplate: (id: string) =>
    request<MarketplaceTemplate>(`/marketplace/${id}`),
  marketplaceClonePreview: (id: string) =>
    request<ClonePreview>(`/marketplace/${id}/clone/preview`),
  cloneTemplate: (id: string) =>
    request<CloneResult>(`/marketplace/${id}/clone`, {
      method: "POST",
      body: JSON.stringify({ confirmed: true }),
    }),

  // multi-agent management
  myAgents: () => request<{ items: AgentSummary[] }>("/agents/mine"),
  myTeam: () =>
    request<{ items: (AgentSummary & { role: string; voice_tone: string | null })[] }>(
      "/agents/team"
    ),
  createAgent: (payload: {
    name: string;
    bio?: string;
    avatar_seed?: string;
    personality_vector?: Record<string, number>;
  }) =>
    request<AgentSummary>("/agents", {
      method: "POST",
      body: JSON.stringify(payload),
    }),
  editAgent: (
    id: string,
    payload: Partial<{
      name: string;
      bio: string;
      avatar_seed: string;
      personality_vector: Record<string, number>;
    }>
  ) =>
    request<AgentSummary>(`/agents/${id}`, {
      method: "PUT",
      body: JSON.stringify(payload),
    }),
  makeAgentPrimary: (id: string) =>
    request<AgentSummary>(`/agents/${id}/make-primary`, { method: "PUT" }),
  deleteAgent: (id: string) =>
    request<{ deleted: boolean; id: string }>(`/agents/${id}`, {
      method: "DELETE",
    }),

  // email intelligence
  classifiedEmails: () =>
    request<{
      urgent_count: number;
      drafts_count: number;
      urgent: ClassifiedEmailRow[];
      drafts: ClassifiedEmailRow[];
      informational: ClassifiedEmailRow[];
    }>("/emails/classified"),
  refreshClassifications: () =>
    request<{ classified: number }>("/emails/refresh", { method: "POST" }),
  editEmailDraft: (id: string, body: string) =>
    request<ClassifiedEmailRow>(`/emails/${id}/draft/edit`, {
      method: "POST",
      body: JSON.stringify({ body }),
    }),
  approveEmailDraft: (id: string) =>
    request<ClassifiedEmailRow>(`/emails/${id}/draft/approve`, {
      method: "POST",
    }),
  discardEmailDraft: (id: string) =>
    request<ClassifiedEmailRow>(`/emails/${id}/draft/discard`, {
      method: "POST",
    }),
  dismissEmail: (id: string) =>
    request<{ dismissed: boolean }>(`/emails/${id}/dismiss`, {
      method: "POST",
    }),

  // A2A async messaging
  agentMessages: () =>
    request<{
      agent_id: string;
      agent_name: string;
      unread_count: number;
      thread_count: number;
      threads: AgentMessageThread[];
    }>("/agent/messages"),
  sendAgentMessage: (recipient_agent_id: string, content: string, thread_id?: string) =>
    request<{
      id: string;
      thread_id: string;
      created_at: string;
      hold_until: string | null;
    }>("/agent/send-message", {
      method: "POST",
      body: JSON.stringify({ recipient_agent_id, content, thread_id }),
    }),
  markThreadRead: (thread_id: string) =>
    request<{ marked_read: number }>(`/agent/messages/${thread_id}/mark-read`, {
      method: "POST",
    }),

  // availability
  getAvailability: () =>
    request<{ availability: AgentAvailabilityValue }>("/agent/availability"),
  setAvailability: (availability: AgentAvailabilityValue) =>
    request<{ availability: AgentAvailabilityValue }>("/agent/availability", {
      method: "PUT",
      body: JSON.stringify({ availability }),
    }),

  // agent activity log
  agentActivity: () =>
    request<{ agent_id: string; items: AgentActivityItem[] }>("/agent/activity"),

  // speech profile / personality init (onboarding tone questions)
  initPersonality: (payload: {
    avg_sentence_length: "short" | "medium" | "long";
    formality: "casual" | "mixed" | "formal";
    emoji_usage: "none" | "occasional" | "frequent";
    punctuation_style: "minimal" | "standard" | "heavy";
    signature_word?: string;
  }) =>
    request<{
      avg_sentence_length: string | null;
      formality: string | null;
      emoji_usage: string | null;
      punctuation_style: string | null;
      signature_word: string | null;
    }>("/agent/personality-init", {
      method: "POST",
      body: JSON.stringify(payload),
    }),

  // schedule — per-agent proactive behaviors
  getSchedule: (agentId: string) =>
    request<{ jobs: ScheduleJob[]; auto_post_schedule: string }>(
      `/agents/${agentId}/schedule`
    ),
  updateSchedule: (
    agentId: string,
    payload: Partial<{
      morning_briefing: boolean;
      inbox_monitor: boolean;
      auto_post: "off" | "daily" | "weekly";
    }>
  ) =>
    request<{ jobs: ScheduleJob[]; auto_post_schedule: string }>(
      `/agents/${agentId}/schedule`,
      { method: "PUT", body: JSON.stringify(payload) }
    ),
};
