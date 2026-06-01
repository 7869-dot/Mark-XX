"""Jarvis orchestration — agent task assignments + their results.

Jarvis (the manager agent) assigns tasks to the email/wildcard agents during the
login wake-up. This sprint, the email agent executes "draft a reply" tasks and
stores the draft here for the user to approve/kill. Nothing is ever sent in V1 —
requires_approval is hardcoded True and there is no send path.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, String, Text, ForeignKey, Index

from app.core.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class AgentTaskResult(Base):
    __tablename__ = "agent_task_results"
    __table_args__ = (Index("ix_agent_task_results_user_approved", "user_id", "approved"),)

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # Logical id of the Jarvis-assigned task this result fulfils (not an FK —
    # JarvisContext tasks are ephemeral/cached, results are the durable record).
    task_id = Column(String, nullable=True)
    agent_role = Column(String, nullable=False, default="email")
    draft_content = Column(Text, nullable=False, default="")
    subject_line = Column(String(500), default="")
    recipient_hint = Column(String(200), default="")
    requires_approval = Column(Boolean, nullable=False, default=True)
    # NULL = pending, True = approved, False = rejected/killed.
    approved = Column(Boolean, nullable=True)
    sent_at = Column(DateTime, nullable=True)  # stays NULL in V1 — no send path
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
