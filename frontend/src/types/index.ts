export type PersonalityVector = {
  openness: number;
  directness: number;
  ambition: number;
  sociability: number;
  risk_tolerance: number;
};

export type AgentStatus = "active" | "idle" | "busy" | "sleeping";

export type Agent = {
  id: string;
  user_id: string;
  name: string;
  bio?: string | null;
  personality_vector: PersonalityVector;
  reputation_score: number;
  social_graph: { agent_id: string; relationship_type: string }[];
  status: AgentStatus;
  current_task: string | null;
  total_tasks_completed: number;
  avatar_seed: string;
  created_at: string;
  last_active_at: string | null;
  user_name?: string;
  user_email?: string;
  onboarding_complete?: boolean;
  goals?: string[];
  // Social persona (Sprint 3).
  avatar_url?: string | null;
  interest_tags?: string[];
  voice_tone?: string | null;
  posting_style?: string | null;
  response_style?: string | null;
  core_interests?: string[];
  posting_frequency_bias?: number;
};

export type TaskStatus =
  | "queued"
  | "running"
  | "completed"
  | "failed"
  | "awaiting_human"
  | "rejected";

export type TaskType =
  | "research"
  | "outreach"
  | "scheduling"
  | "analysis"
  | "networking"
  | "negotiation"
  | "monitoring";

export type Task = {
  id: string;
  agent_id: string;
  user_id: string;
  title: string;
  description: string;
  task_type: TaskType;
  status: TaskStatus;
  priority: number;
  result: {
    summary?: string;
    result?: string;
    recommended_action?: string | null;
    requires_human_approval?: boolean;
    approval_reason?: string | null;
  } | null;
  requires_human_approval: boolean;
  triggered_by: "user" | "agent_self" | "agent_to_agent" | "scheduled";
  rejection_feedback: string | null;
  created_at: string;
  started_at: string | null;
  completed_at: string | null;
};

export type AgentStats = {
  // tasks_* are aliased server-side to activity-log counts so existing UI
  // lights up immediately; new code should prefer actions_*.
  tasks_today: number;
  tasks_week: number;
  tasks_total: number;
  actions_today?: number;
  actions_week?: number;
  actions_total?: number;
  raw_tasks_today?: number;
  raw_tasks_week?: number;
  raw_tasks_total?: number;
  connections: number;
  connection_avatars?: { id: string; name: string; avatar_seed: string }[];
  interactions_today: number;
  time_saved_minutes: number;
  time_saved_minutes_week: number;
  reputation_score: number;
};

export type FeedItem = {
  id: string;
  kind: "task" | "awaiting_approval" | "interaction" | "memory";
  ref_id: string;
  title: string;
  description: string;
  timestamp: string;
  status?: string;
  task_type?: string;
  outbound?: boolean;
  other_agent_id?: string;
  compatibility_score?: number;
  importance?: number;
};

export type PublicAgentProfile = {
  id: string;
  name: string;
  user_name: string;
  reputation_score: number;
  personality_vector?: PersonalityVector;
  total_tasks_completed?: number;
  total_interactions?: number;
  status: AgentStatus;
  avatar_seed: string;
  interests?: string[];
  interest_tags?: string[];
  goals?: { title: string; description: string; horizon: string }[];
  bio?: string;
  created_at?: string;
  compatibility_score?: number | null;
};

export type CompatibilityBreakdown = {
  personality: number;
  goal_alignment: number;
  tag_overlap: number;
};

export type Discovery = {
  id: string;
  name: string;
  user_name: string;
  agent: PublicAgentProfile;
  compatibility_score: number;
  breakdown: CompatibilityBreakdown;
  shared_goals: string[];
  reason: string;
};

export type Interaction = {
  id: string;
  outbound: boolean;
  other_agent: PublicAgentProfile | null;
  interaction_type: string;
  initiator_message: string;
  target_response: string | null;
  message: string;
  response: string | null;
  shared_goals: string[];
  status: string;
  compatibility_score: number;
  human_summary: string;
  created_at: string;
  responded_at: string | null;
};

export type Connection = {
  connection_id: string;
  connection_type: string;
  compatibility_score: number;
  human_followed_up: boolean;
  interaction_count: number;
  created_at: string | null;
  agent: PublicAgentProfile;
};

export type NetworkStats = {
  total_agents: number;
  connections_today: number;
  interactions_this_week: number;
  top_interest_tags: { tag: string; count: number }[];
};

export type ApiResponse<T> = {
  success: boolean;
  data: T | null;
  error: string | { code: string; message: string } | null;
  message?: string;
  meta: { timestamp: string; agent_id: string | null };
};
