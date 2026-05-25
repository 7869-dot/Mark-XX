"""Async agent-to-agent messages.

Agents email each other. Persisted so recipients can process them whenever
their owner next comes online (or whenever the 5-min sweeper picks them up).

Threading is loose: a `thread_id` groups a back-and-forth, defaulting to the
first message's own id when the sender doesn't specify one.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Boolean, Text, ForeignKey, Index

from app.core.db import Base


class AgentMessage(Base):
    __tablename__ = "agent_messages"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    sender_agent_id = Column(
        String, ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    recipient_agent_id = Column(
        String, ForeignKey("agents.id", ondelete="CASCADE"),
        nullable=False, index=True,
    )
    thread_id = Column(String, nullable=False, index=True)
    content = Column(Text, nullable=False)

    # Lifecycle: delivered (in recipient's queue) → processed (recipient agent
    # generated a reply) → read (recipient's owner has seen it).
    delivered = Column(Boolean, nullable=False, default=True)
    processed = Column(Boolean, nullable=False, default=False)
    read = Column(Boolean, nullable=False, default=False)

    # Used when an agent's owner is in DND — message is parked until the
    # availability window opens. NULL when ready immediately.
    hold_until = Column(DateTime, nullable=True)

    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)
    processed_at = Column(DateTime, nullable=True)

    __table_args__ = (
        Index("ix_agent_messages_recipient_processed", "recipient_agent_id", "processed"),
        Index("ix_agent_messages_thread", "thread_id", "created_at"),
    )
