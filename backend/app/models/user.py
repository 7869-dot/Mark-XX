import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, JSON, Text, Boolean
from sqlalchemy.orm import relationship

from app.core.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class User(Base):
    __tablename__ = "users"

    id = Column(String, primary_key=True, default=_uuid)
    email = Column(String, unique=True, nullable=False, index=True)
    name = Column(String, nullable=False)
    avatar_url = Column(String, nullable=True)
    google_id = Column(String, unique=True, nullable=True, index=True)
    goals = Column(JSON, default=list)
    onboarded = Column(JSON, default=lambda: {"completed": False, "step": 0})
    # Source of truth for the 3-step new-user onboarding gate.
    onboarding_complete = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    last_login_at = Column(DateTime, default=datetime.utcnow)

    # Google integration tokens — stored Fernet-encrypted (see google_auth.py).
    google_access_token = Column(Text, nullable=True)
    google_refresh_token = Column(Text, nullable=True)
    google_token_expiry = Column(DateTime, nullable=True)
    google_scopes = Column(Text, nullable=True)
    gmail_connected = Column(Boolean, default=False)
    calendar_connected = Column(Boolean, default=False)

    # Multi-agent schema: User.agents holds the full collection (cascade lives
    # here), while User.agent is a read-only view onto the single is_primary
    # row — keeps every `user.agent` callsite working without code changes,
    # but the schema can grow into a true multi-agent product cleanly.
    agents = relationship(
        "Agent",
        back_populates="user",
        cascade="all, delete-orphan",
    )
    agent = relationship(
        "Agent",
        primaryjoin="and_(User.id == Agent.user_id, Agent.is_primary == True)",
        foreign_keys="Agent.user_id",
        uselist=False,
        viewonly=True,
    )
    tasks = relationship("Task", back_populates="user", cascade="all, delete-orphan")
