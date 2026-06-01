"""Jarvis command-mode draft queues (Sprint 3A).

ScheduleDraft (calendar mode) and PostDraft (post mode) are approval queues —
nothing leaves the system from here in V1. Calendar write + social publish stay
gated behind explicit user approval (and real OAuth send is a later sprint).

IMPORTANT: PostDraft is NOT the social feed. The feed_autopost / world_post
sweeps operate exclusively on AgentPost/PendingPost and never read post_drafts.
A post only reaches the social layer after the posting agent's approval flow.
"""
import uuid
from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Integer, String, Text, ForeignKey, JSON, Index

from app.core.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class ScheduleDraft(Base):
    __tablename__ = "schedule_drafts"
    __table_args__ = (Index("ix_schedule_drafts_user_approved", "user_id", "approved"),)

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    title = Column(String(500), nullable=False, default="")
    proposed_datetime = Column(DateTime, nullable=True)
    duration_minutes = Column(Integer, nullable=True)
    attendees_hint = Column(JSON, default=list)
    notes = Column(Text, default="")
    # NULL = pending, True = approved, False = rejected. No calendar write in V1.
    approved = Column(Boolean, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class PostDraft(Base):
    __tablename__ = "post_drafts"
    __table_args__ = (Index("ix_post_drafts_user_approved", "user_id", "approved"),)

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=False, default="")
    # Which island this might belong to (free text until Islands ship).
    island_hint = Column(String(200), default="")
    # NULL = pending, True = approved, False = rejected. Approval still routes
    # through the posting agent before anything hits the social layer.
    approved = Column(Boolean, nullable=True)
    posted_at = Column(DateTime, nullable=True)  # stays NULL in V1
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
