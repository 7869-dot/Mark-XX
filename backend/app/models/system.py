import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean, Float, Text

from app.core.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class RefreshToken(Base):
    """Tracks issued refresh tokens so rotation can invalidate the prior one.

    Prevents the JWT refresh race: once a refresh token is used it is marked
    used=True and can never be redeemed again.
    """

    __tablename__ = "refresh_tokens"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, nullable=False, index=True)
    jti = Column(String, unique=True, nullable=False, index=True)
    used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    used_at = Column(DateTime, nullable=True)


class SchedulerLock(Base):
    """Cooperative lock so a job never runs twice concurrently (multi-worker safe)."""

    __tablename__ = "scheduler_locks"

    job_id = Column(String, primary_key=True)
    locked_at = Column(DateTime, default=datetime.utcnow)
    locked = Column(Boolean, default=False, nullable=False)


class ReputationEvent(Base):
    """Event-sourced reputation. reputation_score is recomputed, never mutated."""

    __tablename__ = "reputation_events"

    id = Column(String, primary_key=True, default=_uuid)
    agent_id = Column(String, nullable=False, index=True)
    event_type = Column(String, nullable=False)  # task_approved | task_rejected | interaction_accepted | interaction_declined | inactive_decay | task_completed
    delta = Column(Float, nullable=False)
    reason = Column(Text, default="")
    created_at = Column(DateTime, default=datetime.utcnow)
