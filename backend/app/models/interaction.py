import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Enum, Float, JSON, Boolean

from app.core.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class InteractionType(str, enum.Enum):
    introduction = "introduction"
    collaboration_request = "collaboration_request"
    information_exchange = "information_exchange"
    referral = "referral"
    negotiation = "negotiation"
    goal_alignment = "goal_alignment"  # added per A2A spec


class InteractionStatus(str, enum.Enum):
    pending = "pending"  # added per A2A spec
    sent = "sent"
    responded = "responded"
    accepted = "accepted"
    declined = "declined"
    expired = "expired"


class ConnectionType(str, enum.Enum):
    discovered = "discovered"
    introduced = "introduced"
    collaborated = "collaborated"
    following = "following"


class AgentInteraction(Base):
    __tablename__ = "agent_interactions"

    id = Column(String, primary_key=True, default=_uuid)
    initiator_agent_id = Column(String, ForeignKey("agents.id"), nullable=False, index=True)
    target_agent_id = Column(String, ForeignKey("agents.id"), nullable=False, index=True)
    interaction_type = Column(Enum(InteractionType), nullable=False, default=InteractionType.introduction)
    # Legacy columns (kept for back-compat with existing a2a.py / smoke_test).
    message = Column(Text, nullable=False)
    response = Column(Text, nullable=True)
    # New per-spec columns, mirrored from message/response on write.
    initiator_message = Column(Text, nullable=True)
    target_response = Column(Text, nullable=True)
    shared_goals = Column(JSON, default=list)
    status = Column(Enum(InteractionStatus), default=InteractionStatus.sent)
    compatibility_score = Column(Float, default=0.0)
    human_a_notified = Column(Boolean, default=False)
    human_b_notified = Column(Boolean, default=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    responded_at = Column(DateTime, nullable=True)
    last_contacted_at = Column(DateTime, default=datetime.utcnow, index=True)


class AgentConnection(Base):
    """Source of truth for connections (cut over from agents.social_graph)."""

    __tablename__ = "agent_connections"

    id = Column(String, primary_key=True, default=_uuid)
    # Invariant: agent_a_id < agent_b_id (string compare) to dedupe pairs.
    agent_a_id = Column(String, ForeignKey("agents.id"), nullable=False, index=True)
    agent_b_id = Column(String, ForeignKey("agents.id"), nullable=False, index=True)
    compatibility_score = Column(Float, default=0.0)
    connection_type = Column(Enum(ConnectionType), default=ConnectionType.discovered)
    initiated_by = Column(String, ForeignKey("agents.id"), nullable=True)
    human_followed_up = Column(Boolean, default=False)
    interaction_count = Column(Float, default=1)
    created_at = Column(DateTime, default=datetime.utcnow)


class AgentDiscoveryLog(Base):
    __tablename__ = "agent_discovery_log"

    id = Column(String, primary_key=True, default=_uuid)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False, index=True)
    discovered_agent_id = Column(String, ForeignKey("agents.id"), nullable=False, index=True)
    compatibility_score = Column(Float, default=0.0)
    reason = Column(Text, default="")
    was_acted_on = Column(Boolean, default=False)
    discovered_at = Column(DateTime, default=datetime.utcnow, index=True)


class AgentRecommendation(Base):
    """A person/agent the owner should connect with — produced by the A2A cycle.

    This is the owner-facing output of a network scan: a short ranked list with
    a one-line "why", surfaced on the dashboard when the owner next logs in.
    Distinct from AgentInteraction (agent↔agent contact) and AgentConnection
    (an established edge) — a recommendation is advice *for the human*.
    """

    __tablename__ = "agent_recommendations"

    id = Column(String, primary_key=True, default=_uuid)
    # The owner's agent that produced this recommendation.
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False, index=True)
    # The human the owner should meet (spec column). Always set.
    recommended_user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    # The recommended person's agent — convenience for avatars / profile links.
    recommended_agent_id = Column(String, ForeignKey("agents.id"), nullable=True)
    # Denormalized display name so the card renders without an extra join.
    recommended_name = Column(String, default="")
    reason = Column(Text, default="")
    compatibility_score = Column(Float, default=0.0)
    # What the agent suggests the owner do: connect | follow | dm | comment.
    suggested_action = Column(String, default="connect")
    seen = Column(Boolean, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
