"""Sprint 6 — agent web access, world-aware posting, trust + privacy audit.

Tables:
  topic_interests   — the user's TopicInterestProfile (topic -> weight).
  trust_settings    — per-category posting autonomy (MANUAL | SEMI | AUTO).
  pending_posts     — world-aware drafts awaiting approval / auto-publish.
  privacy_audit_log — every agent action that touches another user's data.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Column, String, DateTime, Float, Text, JSON, ForeignKey, Index, UniqueConstraint,
)

from app.core.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# Trust levels (stored as plain strings — no PG enum, so they evolve freely).
TRUST_MANUAL = "MANUAL"   # user approves every post
TRUST_SEMI = "SEMI"       # agent posts, user is notified
TRUST_AUTO = "AUTO"       # agent posts fully autonomously
TRUST_LEVELS = (TRUST_MANUAL, TRUST_SEMI, TRUST_AUTO)

# The category taxonomy the trust toggles + world pulse bucket topics into.
TOPIC_CATEGORIES = (
    "tech", "sports", "geopolitics", "finance", "science", "culture", "local", "general",
)

# Categories that are sensitive by default — never auto-published regardless of
# trust level (the user must approve). Privacy/philosophy guardrail.
SENSITIVE_CATEGORIES = ("geopolitics",)


class TopicInterest(Base):
    """One row per (user, topic). Weight rises as the user engages a topic."""

    __tablename__ = "topic_interests"
    __table_args__ = (
        UniqueConstraint("user_id", "topic", name="uq_topic_interest"),
        Index("ix_topic_interests_user", "user_id"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    topic = Column(String, nullable=False)
    category = Column(String, default="general")
    weight = Column(Float, default=1.0)
    # "onboarding" | "inferred" | "manual" | "rss" — provenance for transparency.
    source = Column(String, default="manual")
    # Optional RSS feed the user follows for this topic.
    feed_url = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class TrustSetting(Base):
    """Per-category posting autonomy. Absent row => MANUAL (safest default)."""

    __tablename__ = "trust_settings"
    __table_args__ = (UniqueConstraint("user_id", "category", name="uq_trust_setting"),)

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    category = Column(String, nullable=False)
    level = Column(String, nullable=False, default=TRUST_MANUAL)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class PendingPost(Base):
    """A world-aware draft. Grounded in live sources + the user's voice, it
    carries a confidence score and a traceable source list — never hallucinated."""

    __tablename__ = "pending_posts"
    __table_args__ = (Index("ix_pending_posts_agent_status", "agent_id", "status"),)

    id = Column(String, primary_key=True, default=_uuid)
    agent_id = Column(String, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    topic = Column(String, default="")
    category = Column(String, default="general")
    confidence_score = Column(Float, default=0.0)
    # [{title, url}] — the sources the post is grounded in.
    source_list = Column(JSON, default=list)
    # pending | approved | rejected | published
    status = Column(String, nullable=False, default="pending", index=True)
    # Legacy column retained for data compatibility (the public social feed and
    # its agent_posts table were removed in the PA-core purge, so this is no
    # longer a foreign key — just an opaque id slot).
    agent_post_id = Column(String, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    decided_at = Column(DateTime, nullable=True)


class PrivacyAuditLog(Base):
    """Append-only: every agent action that reads or transmits data about
    *another* user. The transparency backbone — surfaced to the owner in the UI."""

    __tablename__ = "privacy_audit_log"
    __table_args__ = (Index("ix_privacy_audit_actor_created", "actor_user_id", "created_at"),)

    id = Column(String, primary_key=True, default=_uuid)
    actor_agent_id = Column(String, ForeignKey("agents.id"), nullable=True, index=True)
    actor_user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    subject_user_id = Column(String, ForeignKey("users.id"), nullable=True, index=True)
    action = Column(String, nullable=False)
    reason = Column(Text, default="")
    # What was shared/derived — already PII-stripped (the audit must not leak).
    audit_metadata = Column(JSON, default=dict)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)
