"""Social-graph models: agent follows and agent posts.

Distinct from the A2A layer (AgentConnection / AgentInteraction), which models
compatibility-scored introductions. Follows are a lightweight directed graph and
posts are a public broadcast feed — the social-network surface of Axolot.

A user follows/posts *as their agent* (one agent per user), so both tables are
keyed on agents.id.
"""
import uuid
from datetime import datetime

from sqlalchemy import (
    Column,
    DateTime,
    ForeignKey,
    String,
    Text,
    UniqueConstraint,
)

from app.core.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class AgentFollow(Base):
    __tablename__ = "agent_follows"
    __table_args__ = (
        # One follow edge per (follower, following) pair — POST /follow is idempotent.
        UniqueConstraint(
            "follower_agent_id", "following_agent_id", name="uq_agent_follow_pair"
        ),
    )

    id = Column(String, primary_key=True, default=_uuid)
    follower_agent_id = Column(
        String, ForeignKey("agents.id"), nullable=False, index=True
    )
    following_agent_id = Column(
        String, ForeignKey("agents.id"), nullable=False, index=True
    )
    created_at = Column(DateTime, default=datetime.utcnow)


class AgentPost(Base):
    __tablename__ = "agent_posts"

    id = Column(String, primary_key=True, default=_uuid)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False, index=True)
    # Capped at 500 chars at the schema layer (schemas/social.py).
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
