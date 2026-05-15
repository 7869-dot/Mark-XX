import uuid
import enum
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Text, Enum, Float

from app.core.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class InteractionType(str, enum.Enum):
    introduction = "introduction"
    collaboration_request = "collaboration_request"
    information_exchange = "information_exchange"
    referral = "referral"
    negotiation = "negotiation"


class InteractionStatus(str, enum.Enum):
    sent = "sent"
    responded = "responded"
    accepted = "accepted"
    declined = "declined"
    expired = "expired"


class AgentInteraction(Base):
    __tablename__ = "agent_interactions"

    id = Column(String, primary_key=True, default=_uuid)
    initiator_agent_id = Column(String, ForeignKey("agents.id"), nullable=False, index=True)
    target_agent_id = Column(String, ForeignKey("agents.id"), nullable=False, index=True)
    interaction_type = Column(Enum(InteractionType), nullable=False, default=InteractionType.introduction)
    message = Column(Text, nullable=False)
    response = Column(Text, nullable=True)
    status = Column(Enum(InteractionStatus), default=InteractionStatus.sent)
    compatibility_score = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)
    responded_at = Column(DateTime, nullable=True)
    last_contacted_at = Column(DateTime, default=datetime.utcnow, index=True)
