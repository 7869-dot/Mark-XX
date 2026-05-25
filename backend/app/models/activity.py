"""Append-only log of what the agent did.

Powers the live activity feed ("Your agent classified 12 emails", "Replied
to Priya's agent"). Tiny rows, queried by agent_id ordered desc.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Enum, JSON, ForeignKey, Index

from app.core.db import Base


class ActivityType(str, enum.Enum):
    email_classified = "email_classified"
    email_drafted = "email_drafted"
    email_sent = "email_sent"
    a2a_sent = "a2a_sent"
    a2a_received = "a2a_received"
    a2a_replied = "a2a_replied"
    chat_handled = "chat_handled"
    task_completed = "task_completed"
    reminder_scheduled = "reminder_scheduled"
    memory_captured = "memory_captured"
    other = "other"


class AgentActivityLog(Base):
    __tablename__ = "agent_activity_log"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    agent_id = Column(
        String, ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    action_type = Column(Enum(ActivityType), nullable=False)
    description = Column(String, nullable=False, default="")
    # Free-form payload (counts, refs, etc.) — kept tiny on purpose.
    activity_metadata = Column(JSON, nullable=False, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    __table_args__ = (
        Index("ix_activity_agent_created", "agent_id", "created_at"),
    )
