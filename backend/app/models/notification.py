"""User-facing notifications — the re-engagement surface.

An agent does things while its owner is away (connects, posts, gets reactions,
finds people to meet). Each becomes a Notification row the owner sees in the
navbar bell. Tiny rows, queried by user_id ordered desc.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Boolean, Text, ForeignKey, Index

from app.core.db import Base


class NotificationType:
    """Stored as plain strings (not a PG enum) so new types never need ALTER TYPE."""

    AGENT_INTERACTION = "agent_interaction"
    AGENT_POST = "agent_post"
    SOCIAL_REACTION = "social_reaction"
    RECOMMENDATION = "recommendation"
    INVITE = "invite"


class Notification(Base):
    __tablename__ = "notifications"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(
        String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True
    )
    type = Column(String, nullable=False)
    title = Column(String, nullable=False)
    body = Column(Text, nullable=False, default="")
    # Where clicking the notification should take the user (SPA path), or NULL.
    link = Column(String, nullable=True)
    seen = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)

    __table_args__ = (
        Index("ix_notifications_user_seen_created", "user_id", "seen", "created_at"),
    )
