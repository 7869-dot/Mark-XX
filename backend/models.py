"""SQLAlchemy ORM models for the Axolotl A2A layer.

Design notes
────────────
• All IDs are UUID strings — portable, no auto-increment races.
• JSON columns (tags, embedding) are stored as TEXT in SQLite; SQLAlchemy
  handles (de)serialisation transparently.
• `updated_at` is refreshed in Python (not via DB triggers) for SQLite compat.
• Private fields (email, real name) are NEVER stored on AgentCard — only the
  public profile the user explicitly published.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Boolean, Column, DateTime, Float, ForeignKey,
    Integer, JSON, String, Text,
)

from db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


def _now() -> datetime:
    return datetime.utcnow()


# ── Users ──────────────────────────────────────────────────────────────────────

class User(Base):
    __tablename__ = "users"

    id           = Column(String, primary_key=True, default=_uuid)
    display_name = Column(String, nullable=False)
    created_at   = Column(DateTime, default=_now)


# ── Agent Cards ────────────────────────────────────────────────────────────────

class AgentCard(Base):
    """The ONLY thing other agents see.  No private fields allowed here."""
    __tablename__ = "agent_cards"

    id           = Column(String, primary_key=True, default=_uuid)
    user_id      = Column(String, ForeignKey("users.id"), unique=True, nullable=False)

    # Public profile fields
    display_name = Column(String, nullable=False)
    public_bio   = Column(Text, default="")
    building     = Column(Text, default="")      # what they're building
    looking_for  = Column(Text, default="")      # what collaboration they want
    can_offer    = Column(Text, default="")      # what they bring to the table
    tags         = Column(JSON, default=list)    # ["fintech", "open-source", ...]

    # Similarity vector (list[float]).  Computed from text fields.
    # TODO: replace with a real embedding model (e.g. voyage-3) when ready.
    embedding    = Column(JSON, default=list)

    is_public    = Column(Boolean, default=True)  # false = hidden from discovery
    a2a_enabled  = Column(Boolean, default=True)  # opt-in to autonomous matchmaking

    updated_at   = Column(DateTime, default=_now)


# ── Connection Proposals ───────────────────────────────────────────────────────

class ConnectionProposal(Base):
    """
    Lifecycle: proposed → (approved_by_a + approved_by_b → approved) | rejected | expired

    Safety: only the approved state unlocks contact exchange.  All earlier
    states are opaque — neither party sees the other's contact info.
    """
    __tablename__ = "connection_proposals"

    id                     = Column(String, primary_key=True, default=_uuid)
    agent_a_id             = Column(String, ForeignKey("agent_cards.id"), nullable=False)
    agent_b_id             = Column(String, ForeignKey("agent_cards.id"), nullable=False)

    # candidate | negotiating | proposed | approved_by_a | approved_by_b
    # | approved | rejected | expired
    status                 = Column(String, default="proposed", nullable=False)

    match_score            = Column(Float, default=0.0)
    match_reason           = Column(Text, default="")
    proposed_collaboration = Column(Text, default="")  # the idea
    what_each_brings       = Column(Text, default="")
    confidence             = Column(Float, default=0.0)

    created_at             = Column(DateTime, default=_now)
    updated_at             = Column(DateTime, default=_now)


# ── A2A Negotiation Messages ───────────────────────────────────────────────────

class A2AMessage(Base):
    """Full transcript of the inter-agent negotiation (append-only log)."""
    __tablename__ = "a2a_messages"

    id          = Column(String, primary_key=True, default=_uuid)
    proposal_id = Column(String, ForeignKey("connection_proposals.id"), nullable=False)
    from_agent_id = Column(String, ForeignKey("agent_cards.id"), nullable=False)
    role        = Column(String, nullable=False)   # "agent_a" | "agent_b"
    content     = Column(Text, nullable=False)
    turn        = Column(Integer, nullable=False)
    created_at  = Column(DateTime, default=_now)


# ── Briefings ──────────────────────────────────────────────────────────────────

class Briefing(Base):
    """
    Human-readable summary delivered to a user on their next login.
    One briefing per user per proposal (both users in a pair get their own).
    """
    __tablename__ = "briefings"

    id            = Column(String, primary_key=True, default=_uuid)
    user_id       = Column(String, ForeignKey("users.id"), nullable=False)
    proposal_id   = Column(String, ForeignKey("connection_proposals.id"), nullable=False)

    # Written by the matchmaker after the negotiation verdict
    summary        = Column(Text, nullable=False)
    recommendation = Column(Text, nullable=False)

    seen       = Column(Boolean, default=False)
    created_at = Column(DateTime, default=_now)
