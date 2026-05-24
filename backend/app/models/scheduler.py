"""Scheduler control surface: per-agent job toggles and inbox-alert dedupe.

Distinct from system.SchedulerLock — that's the cross-process job lock owned by
APScheduler. These rows are the *user-facing* schedule state: what the agent is
allowed to do on its own, and what it has already done.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    String,
    UniqueConstraint,
)

from app.core.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# Allowed job_type strings (kept as plain strings, not enum, to avoid a
# Postgres ALTER TYPE migration every time we add a behavior).
JOB_MORNING_BRIEFING = "morning_briefing"
JOB_INBOX_MONITOR = "inbox_monitor"
JOB_AUTO_POST = "auto_post"
ALL_JOB_TYPES = (JOB_MORNING_BRIEFING, JOB_INBOX_MONITOR, JOB_AUTO_POST)


class ScheduledJob(Base):
    __tablename__ = "scheduled_jobs"
    __table_args__ = (
        UniqueConstraint("agent_id", "job_type", name="uq_scheduled_jobs_agent_type"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False, index=True)
    job_type = Column(String, nullable=False, index=True)
    # Free-form cron-ish hint surfaced to the UI; the actual scheduling is done
    # by a small set of APScheduler cron jobs that fan out per-agent based on
    # `enabled`. For auto_post this is "daily" / "weekly".
    cron_expr = Column(String, nullable=True)
    enabled = Column(Boolean, default=False, nullable=False)
    last_run = Column(DateTime, nullable=True)
    next_run = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class AgentAlert(Base):
    __tablename__ = "agent_alerts"
    __table_args__ = (
        UniqueConstraint("agent_id", "message_id", name="uq_agent_alerts_agent_msg"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False, index=True)
    # For urgent_email / vip_email this is the Gmail message id. Kept opaque so
    # alert_type can grow (e.g. "calendar_conflict") without schema changes.
    message_id = Column(String, nullable=False)
    alert_type = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
