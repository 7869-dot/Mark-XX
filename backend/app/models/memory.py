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
    # Jarvis command mode this turn was in: default|email|schedule|research|post.
    # NULL for legacy/plain chat. The summarizer ignores it (reads role/content),
    # so Jarvis-mode turns feed ConversationSummary automatically.
    mode = Column(String, nullable=True)
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

    # === Structured speech-mirror fields (Phase 3) ===
    # Each enum-shaped column stores a short token so the chat prompt can
    # inject it verbatim. NULLs mean "not yet inferred" — the prompt block
    # then falls back to the freeform `communication_style` text.
    avg_sentence_length = Column(String(16), nullable=True)  # short | medium | long
    formality = Column(String(16), nullable=True)            # casual | mixed | formal
    emoji_usage = Column(String(16), nullable=True)          # none | occasional | frequent
    punctuation_style = Column(String(16), nullable=True)    # minimal | standard | heavy
    signature_word = Column(String(64), nullable=True)
    sample_phrases = Column(JSON, default=list)              # short list of verbatim phrases

    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
