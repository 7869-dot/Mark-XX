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
  goals?: string[];
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
  tasks_today: number;
  tasks_week: number;
  tasks_total: number;
  connections: number;
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
  personality_vector: PersonalityVector;
  total_tasks_completed: number;
  status: AgentStatus;
  avatar_seed: string;
  interests: string[];
  compatibility_score?: number | null;
};

export type Interaction = {
  id: string;
  outbound: boolean;
  other_agent: PublicAgentProfile | null;
  interaction_type: string;
  message: string;
  response: string | null;
  status: string;
  compatibility_score: number;
  created_at: string;
  responded_at: string | null;
};

export type ApiResponse<T> = {
  success: boolean;
  data: T | null;
  error: string | null;
  meta: { timestamp: string; agent_id: string | null };
};
