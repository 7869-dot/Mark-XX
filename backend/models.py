"""SQLAlchemy ORM models for the Axolotl A2A layer.

Design notes
────────────
• All IDs are UUID strings — portable, no auto-increment races.
• JSON columns (tags, embedding) stored as TEXT in SQLite; SQLAlchemy handles serde.
• `updated_at` refreshed in Python (not via DB triggers) for SQLite compat.
• Private fields (email, OAuth tokens) are NEVER on AgentCard — only public profile.
• OAuth tokens are stored encrypted at rest (see auth.py encrypt_token).

Adding new columns
──────────────────
SQLite does not support modifying existing columns.  When a new column is added
here, either:
  (a) delete axolotl.db and restart (dev), or
  (b) run `ALTER TABLE <table> ADD COLUMN ...` manually.
`init_db()` in db.py also calls `upgrade_db()` which does option (b) for known
new columns automatically.
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

    # Added in Phase 2 — nullable so seed users (no OAuth) still work.
    # upgrade_db() in db.py adds these columns to existing DBs automatically.
    google_sub   = Column(String, unique=True, nullable=True)   # Google's stable user ID
    email        = Column(String, nullable=True)                 # from Google id_token


# ── OAuth Tokens ───────────────────────────────────────────────────────────────

class OAuthToken(Base):
    """
    Server-side storage for Google OAuth tokens.

    SECURITY:
    • access_token_enc and refresh_token_enc are Fernet-encrypted.
    • Raw tokens are NEVER returned to the client — only JWTs are.
    • Refresh happens server-side in auth.get_valid_access_token().
    """
    __tablename__ = "oauth_tokens"

    id                = Column(String, primary_key=True, default=_uuid)
    user_id           = Column(String, ForeignKey("users.id"), unique=True, nullable=False)
    access_token_enc  = Column(Text, nullable=False)   # encrypted
    refresh_token_enc = Column(Text, default="")       # encrypted; may be empty on re-auth
    token_type        = Column(String, default="Bearer")
    scopes            = Column(Text, default="")       # space-separated scope list
    expires_at        = Column(DateTime, nullable=False)
    updated_at        = Column(DateTime, default=_now)


# ── Agent Cards ────────────────────────────────────────────────────────────────

class AgentCard(Base):
    """The ONLY thing other agents see.  No private fields allowed here."""
    __tablename__ = "agent_cards"

    id           = Column(String, primary_key=True, default=_uuid)
    user_id      = Column(String, ForeignKey("users.id"), unique=True, nullable=False)

    display_name = Column(String, nullable=False)
    public_bio   = Column(Text, default="")
    building     = Column(Text, default="")
    looking_for  = Column(Text, default="")
    can_offer    = Column(Text, default="")
    tags         = Column(JSON, default=list)
    # TODO: replace with a real embedding model (voyage-3, text-embedding-3-small)
    embedding    = Column(JSON, default=list)

    is_public    = Column(Boolean, default=True)
    a2a_enabled  = Column(Boolean, default=True)
    updated_at   = Column(DateTime, default=_now)


# ── Connection Proposals ───────────────────────────────────────────────────────

class ConnectionProposal(Base):
    """
    Lifecycle: proposed → approved_by_a / approved_by_b → approved | rejected | expired

    Safety: only the 'approved' state unlocks contact exchange.
    TODO: contact exchange must require MUTUAL approval (both users approve their
    own briefing) before any contact data is shared — one user cannot consent on
    the other's behalf.  The current state machine enforces both approvals before
    status reaches 'approved', but the actual secure exchange mechanism is not yet
    implemented (see api/a2a.py approve_briefing).
    """
    __tablename__ = "connection_proposals"

    id                     = Column(String, primary_key=True, default=_uuid)
    agent_a_id             = Column(String, ForeignKey("agent_cards.id"), nullable=False)
    agent_b_id             = Column(String, ForeignKey("agent_cards.id"), nullable=False)
    status                 = Column(String, default="proposed", nullable=False)
    match_score            = Column(Float, default=0.0)
    match_reason           = Column(Text, default="")
    proposed_collaboration = Column(Text, default="")
    what_each_brings       = Column(Text, default="")
    confidence             = Column(Float, default=0.0)
    created_at             = Column(DateTime, default=_now)
    updated_at             = Column(DateTime, default=_now)


# ── A2A Negotiation Messages ───────────────────────────────────────────────────

class A2AMessage(Base):
    __tablename__ = "a2a_messages"

    id            = Column(String, primary_key=True, default=_uuid)
    proposal_id   = Column(String, ForeignKey("connection_proposals.id"), nullable=False)
    from_agent_id = Column(String, ForeignKey("agent_cards.id"), nullable=False)
    role          = Column(String, nullable=False)
    content       = Column(Text, nullable=False)
    turn          = Column(Integer, nullable=False)
    created_at    = Column(DateTime, default=_now)


# ── Briefings ──────────────────────────────────────────────────────────────────

class Briefing(Base):
    __tablename__ = "briefings"

    id             = Column(String, primary_key=True, default=_uuid)
    user_id        = Column(String, ForeignKey("users.id"), nullable=False)
    proposal_id    = Column(String, ForeignKey("connection_proposals.id"), nullable=False)
    summary        = Column(Text, nullable=False)
    recommendation = Column(Text, nullable=False)
    seen           = Column(Boolean, default=False)
    created_at     = Column(DateTime, default=_now)
