"""Persisted Gmail classifications.

Email content itself stays in Gmail — we only persist the classification verdict,
the agent's drafted reply for AGENT_HANDLEABLE messages, and surfacing flags.
"""
import enum
import uuid
from datetime import datetime

from sqlalchemy import Column, String, DateTime, Enum, Boolean, Text, ForeignKey, Index

from app.core.db import Base


class EmailCategory(str, enum.Enum):
    urgent_human = "URGENT_HUMAN"
    informational = "INFORMATIONAL"
    spam = "SPAM"
    agent_handleable = "AGENT_HANDLEABLE"


class ClassifiedEmail(Base):
    __tablename__ = "classified_emails"

    id = Column(String, primary_key=True, default=lambda: str(uuid.uuid4()))
    user_id = Column(String, ForeignKey("users.id", ondelete="CASCADE"), nullable=False, index=True)
    agent_id = Column(String, ForeignKey("agents.id", ondelete="CASCADE"), nullable=True)

    # Gmail message id — natural primary candidate, but we keep our own uuid so
    # the row can outlive the message in Gmail (e.g., user-archived).
    email_id = Column(String, nullable=False, index=True)
    thread_id = Column(String, nullable=True)
    sender = Column(String, nullable=False, default="")
    sender_email = Column(String, nullable=False, default="")
    subject = Column(String, nullable=False, default="")
    snippet = Column(Text, nullable=False, default="")

    category = Column(Enum(EmailCategory), nullable=False, index=True)
    reason = Column(Text, nullable=False, default="")
    suggested_action = Column(Text, nullable=True)

    # For AGENT_HANDLEABLE rows the agent pre-drafts a reply; one click sends.
    drafted_reply = Column(Text, nullable=True)
    draft_status = Column(String, nullable=False, default="pending")  # pending | approved | edited | discarded | sent

    dismissed = Column(Boolean, nullable=False, default=False)
    created_at = Column(DateTime, default=datetime.utcnow, nullable=False)

    __table_args__ = (
        Index("ix_classified_emails_user_category", "user_id", "category"),
        Index("ix_classified_emails_email", "user_id", "email_id", unique=True),
    )
