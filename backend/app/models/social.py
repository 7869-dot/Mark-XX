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
    Boolean,
    Column,
    DateTime,
    ForeignKey,
    Index,
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
    # "standard" — written by a user via POST /agents/{id}/post, or by an
    # auto-generated proactive sweep.
    # "ghost" / "auto_feed" — autonomously generated (see is_agent_post).
    # "system_notice" — emitted by the scheduler when a sweep degrades
    # gracefully on a Gemini quota/503/rate error, so the feed isn't silent.
    post_type = Column(String, default="standard", nullable=False)
    # True when the agent generated this post autonomously (ghost / scheduled /
    # auto_feed). False for posts the human wrote via POST /agents/{id}/post.
    # Drives the unified feed's author_type tag and the "AI" badge on the card.
    is_agent_post = Column(Boolean, nullable=False, default=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)

    __table_args__ = (
        # Hot path: the unified feed pulls the latest posts platform-wide.
        Index("ix_agent_posts_created", "created_at"),
    )


class PostLike(Base):
    """A user's like on a post. One row per (post, user) — toggling deletes it."""

    __tablename__ = "post_likes"
    __table_args__ = (
        UniqueConstraint("post_id", "user_id", name="uq_post_like"),
        Index("ix_post_likes_post", "post_id"),
    )

    id = Column(String, primary_key=True, default=_uuid)
    post_id = Column(
        String, ForeignKey("agent_posts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)


class PostComment(Base):
    """A user's comment on a post (authored as the human; rendered as their agent)."""

    __tablename__ = "post_comments"
    __table_args__ = (Index("ix_post_comments_post_created", "post_id", "created_at"),)

    id = Column(String, primary_key=True, default=_uuid)
    post_id = Column(
        String, ForeignKey("agent_posts.id", ondelete="CASCADE"), nullable=False, index=True
    )
    author_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    content = Column(Text, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow, index=True)
