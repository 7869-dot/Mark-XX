"""Jarvis memory architecture (Section 2 + 3 of the manager overhaul).

Three tables:
  user_profiles      — the per-user memory profile Jarvis builds and tunes over
                       time: interests, hates, goals, communication_style,
                       opportunity_preferences, and a rolling feedback_log. This
                       is distinct from `user_personalities` (which the chat
                       summarizer derives automatically) — `user_profiles` is the
                       explicit, onboarding-seeded profile Jarvis reasons from and
                       the source for build_jarvis_prompt().
  web_scout_results  — opportunities the web_agent surfaces, each rated for
                       relevance and (later) thumbs-up/down by the user.
  agent_run_log      — one row per sub-agent run: when it ran, a one-line report
                       summary, and status. Powers the agent status panel.

Runtime DDL is driven by Base.metadata.create_all (creates missing tables on
every boot) + core.schema_sync (columns/indexes). Alembic 0014 keeps the
migration history complete for fresh prod setups.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey, Index, JSON, String, Text,
)

from app.core.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# Web scout categories the web_agent scans (all active by default, re-weighted
# by the user's feedback_log over time). Plain strings so the taxonomy evolves
# without an enum migration.
WEB_CATEGORIES = (
    "freelance",       # Fiverr/Upwork/LinkedIn/Wellfound gigs + job posts
    "learning",        # courses, papers, fast.ai, Karpathy, NPTEL, Coursera
    "certification",   # certs relevant to the user's goals
    "news",            # news & trends in the user's areas
    "investment",      # income/investment opportunities matching their skills
    "event",           # hackathons, competitions, events
)

# Feedback verbs stored on web_scout_results.feedback (NULL until the user rates).
FEEDBACK_USEFUL = "useful"
FEEDBACK_NOT_USEFUL = "not_useful"
FEEDBACK_VALUES = (FEEDBACK_USEFUL, FEEDBACK_NOT_USEFUL)


class UserProfile(Base):
    """Jarvis's persistent memory profile for one user. One row per user."""

    __tablename__ = "user_profiles"
    __table_args__ = (Index("ix_user_profiles_user", "user_id", unique=True),)

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(
        String, ForeignKey("users.id", ondelete="CASCADE"),
        unique=True, nullable=False, index=True,
    )
    # Topics the user cares about: ["AI infra", "startups", ...].
    interests = Column(JSON, default=list)
    # Things to avoid / dismissed: ["Java jobs", "crypto hype", ...].
    hates = Column(JSON, default=list)
    # {"short_term": [...], "long_term": [...]} or a flat list of goal strings.
    goals = Column(JSON, default=dict)
    # Inferred voice: "direct, casual, brief" — fed into every sub-agent prompt.
    communication_style = Column(Text, default="")
    # Which opportunity categories the user wants surfaced (subset of
    # WEB_CATEGORIES) — defaults to all when empty.
    opportunity_preferences = Column(JSON, default=list)
    # Rolling log of liked/dismissed items: [{result_id, category, feedback, at}].
    # The web_agent reads this to re-weight future scans.
    feedback_log = Column(JSON, default=list)
    # Jarvis's own onboarding (the 5 questions) — distinct from the app's
    # 3-step new-user gate on users.onboarding_complete.
    onboarding_complete = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class WebScoutResult(Base):
    """One opportunity surfaced by the web_agent for a user."""

    __tablename__ = "web_scout_results"
    __table_args__ = (
        Index("ix_web_scout_user_created", "user_id", "created_at"),
        Index("ix_web_scout_user_category", "user_id", "category"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(
        String, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    title = Column(Text, nullable=False, default="")
    url = Column(Text, nullable=False, default="")
    summary = Column(Text, nullable=False, default="")
    category = Column(String(32), nullable=False, default="news")
    relevance_score = Column(Float, nullable=False, default=0.0)
    # NULL until the user rates it; then "useful" | "not_useful".
    feedback = Column(String(16), nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False, index=True)


class AgentRunLog(Base):
    """One row per sub-agent run — drives the status panel (last run, summary,
    status). agent_name is the internal role: email_agent | feed_agent | web_agent."""

    __tablename__ = "agent_run_log"
    __table_args__ = (Index("ix_agent_run_log_user_agent_ran", "user_id", "agent_name", "ran_at"),)

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(
        String, ForeignKey("users.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    agent_name = Column(String(32), nullable=False)
    ran_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    report_summary = Column(Text, default="")
    # "ok" | "error" | "running" | "skipped"
    status = Column(String(16), nullable=False, default="ok")
