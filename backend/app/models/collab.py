"""Sprint 6 — private inter-agent collaboration.

When two users mutually follow each other their agents open a CollaborationSession
and exchange *anonymized intent signals* (no PII) over the a2a bus. From the
overlap an agent proposes a collaboration, surfaced to each owner as a suggestion.
Raw inter-agent messages are stored encrypted (services.agent_collab); only the
PII-stripped derived signal/proposal is ever shown to a user.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Text, JSON, ForeignKey, Index, UniqueConstraint

from app.core.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# Session states.
SESSION_ACTIVE = "active"
SESSION_PROPOSED = "proposed"
SESSION_CLOSED = "closed"

# Proposal states.
PROPOSAL_PENDING = "pending"
PROPOSAL_ACCEPTED = "accepted"
PROPOSAL_DECLINED = "declined"


class CollaborationSession(Base):
    """A private channel between two mutually-following agents. agent_a_id <
    agent_b_id (string order) so a pair maps to exactly one session."""

    __tablename__ = "collaboration_sessions"
    __table_args__ = (
        UniqueConstraint("agent_a_id", "agent_b_id", name="uq_collab_pair"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    agent_a_id = Column(String, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_b_id = Column(String, ForeignKey("agents.id", ondelete="CASCADE"), nullable=False, index=True)
    state = Column(String, nullable=False, default=SESSION_ACTIVE)
    # Encrypted transcript of the raw a2a exchange (Fernet). Never returned to a
    # client — it exists only so the engine can resume a negotiation.
    encrypted_transcript = Column(Text, nullable=True)
    last_run_at = Column(DateTime, nullable=True)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)


class CollaborationProposal(Base):
    """A surfaced suggestion: 'your agent found a potential collaborator'.
    intent fields are anonymized (no PII) by construction + privacy_filter."""

    __tablename__ = "collaboration_proposals"
    __table_args__ = (Index("ix_collab_proposals_recipient", "to_user_id", "status"),)

    id = Column(String, primary_key=True, default=_uuid)
    session_id = Column(String, ForeignKey("collaboration_sessions.id", ondelete="CASCADE"), nullable=False, index=True)
    from_agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    to_agent_id = Column(String, ForeignKey("agents.id"), nullable=False)
    # The owner who sees this proposal in their Collaboration Inbox.
    to_user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    # Anonymized: "Someone is looking for a backend co-founder."
    from_intent = Column(Text, default="")
    proposal_text = Column(Text, default="")
    status = Column(String, nullable=False, default=PROPOSAL_PENDING, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
    decided_at = Column(DateTime, nullable=True)
