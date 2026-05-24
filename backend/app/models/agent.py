import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, JSON, Float, Integer, ForeignKey, Text, Enum
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


DEFAULT_PERSONALITY = {
    "openness": 0.5,
    "directness": 0.5,
    "ambition": 0.5,
    "sociability": 0.5,
    "risk_tolerance": 0.5,
}


class Agent(Base):
    __tablename__ = "agents"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), unique=True, nullable=False, index=True)
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
    created_at = Column(DateTime, default=datetime.utcnow)
    last_active_at = Column(DateTime, default=datetime.utcnow)

    user = relationship("User", back_populates="agent")
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
