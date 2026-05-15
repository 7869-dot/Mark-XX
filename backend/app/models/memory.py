import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, JSON, ForeignKey, Text, Integer

from app.core.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class ChatHistory(Base):
    __tablename__ = "chat_history"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    role = Column(String, nullable=False)  # user | agent
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)


class ConversationSummary(Base):
    __tablename__ = "conversation_summaries"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    summary = Column(Text, nullable=False)
    message_count = Column(Integer, default=0)
    created_at = Column(DateTime, default=datetime.utcnow)


class UserPersonality(Base):
    __tablename__ = "user_personalities"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, ForeignKey("users.id"), unique=True, nullable=False, index=True)
    traits = Column(JSON, default=dict)
    interests = Column(JSON, default=list)
    communication_style = Column(Text, default="")
    notes = Column(Text, default="")
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
