import uuid
from datetime import datetime
from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    Enum,
    Float,
    ForeignKey,
    Index,
    Integer,
    JSON,
    String,
    Text,
    text,
)
from sqlalchemy.orm import relationship
import enum

from app.core.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class AgentStatus(str, enum.Enum):
    active = "active"
    idle = "idle"
    busy = "busy"
    sleeping = "sleeping"


class AgentAvailability(str, enum.Enum):
    """User-controlled availability window for proactive behaviors + A2A.

    - always_on:      agent acts at any hour; A2A processed immediately.
    - business_hours: agent acts 9–18 local; A2A held outside window.
    - dnd:            agent suppresses proactive output; A2A batched until lifted.
    """
    always_on = "always_on"
    business_hours = "business_hours"
    dnd = "dnd"


DEFAULT_PERSONALITY = {
    "openness": 0.5,
    "directness": 0.5,
    "ambition": 0.5,
    "sociability": 0.5,
    "risk_tolerance": 0.5,
}


class Agent(Base):
    __tablename__ = "agents"
    # Replaces the legacy UNIQUE(user_id) constraint — many agents may belong
    # to one user, but only ONE may be is_primary=TRUE per user. Enforced at
    # the DB level with a partial unique index (PG + SQLite both support it).
    __table_args__ = (
        Index(
            "uq_primary_agent_per_user",
            "user_id",
            unique=True,
            postgresql_where=text("is_primary = true"),
            sqlite_where=text("is_primary = 1"),
        ),
    )

    id = Column(String, primary_key=True, default=_uuid)
    # NOTE: no `unique=True` — multi-agent schema. Use Agent.is_primary to
    # find "the" agent for a user (or the new get_primary_agent helper).
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    # Exactly one row per user can be is_primary=True (enforced by the partial
    # unique index above). Existing rows backfill to True via migration 0010
    # so app behavior is unchanged until the multi-agent UI ships.
    is_primary = Column(Boolean, default=True, nullable=False)
    name = Column(String, nullable=False)
    # Short self-description, set during onboarding; shown on the social profile.
    bio = Column(Text, nullable=True)
    personality_vector = Column(JSON, default=lambda: dict(DEFAULT_PERSONALITY))
    # interest_tags: ["AI","startups",...]  — synced from user_personalities.interests
    interest_tags = Column(JSON, default=list)
    # goals: [{title, description, horizon: week|month|year}] — synced from users.goals
    goals = Column(JSON, default=list)
    reputation_score = Column(Float, default=50.0)
    # social_graph kept additively for back-compat; connections are now the
    # source of truth in the agent_connections table (cut over fully).
    social_graph = Column(JSON, default=list)
    status = Column(Enum(AgentStatus), default=AgentStatus.idle)
    current_task = Column(Text, nullable=True)
    total_tasks_completed = Column(Integer, default=0)
    total_interactions = Column(Integer, default=0)
    avatar_seed = Column(String, default=_uuid)
    # Stable system-prompt suffix that overrides default voice — set by
    # marketplace templates; injected by context_builder on every Gemini call.
    system_prompt = Column(Text, nullable=True)
    # 'off' | 'daily' | 'weekly' — drives the auto_post scheduler job.
    auto_post_schedule = Column(String, default="off", nullable=False)
    # User-controlled availability — gates proactive jobs + A2A processing.
    # New rows default to always_on; existing rows backfill via create_all (no
    # migration step needed because SQLite/PG accept NULL for older rows that
    # never had this column — the read path normalizes None to always_on).
    availability = Column(
        Enum(AgentAvailability),
        default=AgentAvailability.always_on,
        nullable=True,
    )

    # ── Social persona (Sprint 3) — makes each agent a distinct individual ──
    # Short tone label: witty | analytical | warm | provocative | poetic | …
    voice_tone = Column(String, nullable=True)
    # How they post: "short takes" | "long threads" | "questions" | "hot takes" | "stories"
    posting_style = Column(String, nullable=True)
    # How they engage others: "Socratic" | "affirming" | "contrarian" | "collaborative"
    response_style = Column(String, nullable=True)
    # 5-10 curated persona topics. Distinct from interest_tags (synced from the
    # user) — core_interests is the agent's stable, public identity.
    core_interests = Column(JSON, default=list)
    # 0.5 = posts less than average, 1.5 = posts more. Scales the autopost odds.
    posting_frequency_bias = Column(Float, default=1.0)
    # Optional hosted avatar; falls back to the deterministic SVG (avatar_seed).
    avatar_url = Column(String, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow)
    last_active_at = Column(DateTime, default=datetime.utcnow)

    # The `agents` collection on User cascades; this back-ref is the inverse.
    user = relationship("User", back_populates="agents")
    memories = relationship("AgentMemory", back_populates="agent", cascade="all, delete-orphan")
    tasks = relationship("Task", back_populates="agent", cascade="all, delete-orphan")

    @property
    def goal_titles(self) -> list:
        out = []
        for g in self.goals or []:
            if isinstance(g, dict):
                out.append(g.get("title") or g.get("description") or "")
            else:
                out.append(str(g))
        return [g for g in out if g]


class AgentMemoryType(str, enum.Enum):
    task_outcome = "task_outcome"
    interaction = "interaction"
    learned_preference = "learned_preference"
    milestone = "milestone"
    # Memories of the agent's own outbound posts — closes the voice-consistency
    # loop in context_builder (Layer 4 of the memory pipeline).
    post_history = "post_history"


class AgentMemory(Base):
    __tablename__ = "agent_memories"

    id = Column(String, primary_key=True, default=_uuid)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False, index=True)
    memory_type = Column(Enum(AgentMemoryType), nullable=False)
    content = Column(Text, nullable=False)
    importance_score = Column(Float, default=0.5)
    created_at = Column(DateTime, default=datetime.utcnow)

    agent = relationship("Agent", back_populates="memories")
