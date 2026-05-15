import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, DateTime, JSON, Integer, ForeignKey, Text, Enum, Boolean
from sqlalchemy.orm import relationship

from app.core.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class TaskType(str, enum.Enum):
    research = "research"
    outreach = "outreach"
    scheduling = "scheduling"
    analysis = "analysis"
    networking = "networking"
    negotiation = "negotiation"
    monitoring = "monitoring"


class TaskStatus(str, enum.Enum):
    queued = "queued"
    running = "running"
    completed = "completed"
    failed = "failed"
    awaiting_human = "awaiting_human"
    rejected = "rejected"


class TaskTrigger(str, enum.Enum):
    user = "user"
    agent_self = "agent_self"
    agent_to_agent = "agent_to_agent"
    scheduled = "scheduled"


class Task(Base):
    __tablename__ = "tasks"

    id = Column(String, primary_key=True, default=_uuid)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    title = Column(String, nullable=False)
    description = Column(Text, nullable=False)
    task_type = Column(Enum(TaskType), nullable=False, default=TaskType.research)
    status = Column(Enum(TaskStatus), nullable=False, default=TaskStatus.queued, index=True)
    priority = Column(Integer, default=3)
    result = Column(JSON, nullable=True)
    requires_human_approval = Column(Boolean, default=False)
    triggered_by = Column(Enum(TaskTrigger), default=TaskTrigger.user)
    rejection_feedback = Column(Text, nullable=True)
    task_timeout_minutes = Column(Integer, default=10)
    created_at = Column(DateTime, default=datetime.utcnow)
    started_at = Column(DateTime, nullable=True)
    completed_at = Column(DateTime, nullable=True)

    agent = relationship("Agent", back_populates="tasks")
    user = relationship("User", back_populates="tasks")
