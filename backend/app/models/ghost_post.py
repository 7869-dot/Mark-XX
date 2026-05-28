"""Ghost posting: the agent speaks for its owner, even while the owner is offline.

The core differentiator — an agent keeps the owner's presence alive 24/7 by
generating first-person posts grounded in the owner's memory layers
(UserPersonality + ConversationSummary + AgentMemory).

Distinct from social.AgentPost, which is the public feed row. A GhostPost is the
*generation record*: what was produced, from which rotation slot, and whether it
was auto-posted to the feed or held for the owner to review. When a ghost post
goes live it spawns a real AgentPost (post_type="ghost"); `agent_post_id` links
the two so the morning digest can show "what your agent posted overnight".

post_type is kept as a plain string (not a PG enum) for the same reason
scheduled_jobs.job_type is — adding a rotation category shouldn't need ALTER TYPE.
"""
import uuid
from datetime import datetime

from sqlalchemy import Column, DateTime, ForeignKey, String, Text

from app.core.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


# Rotation categories the engine cycles through (spec §7a-d).
POST_OWNERS_DAY = "owners_day"          # what the owner did today, from memory
POST_WORLD_OPINION = "world_opinion"    # owner's inferred stance on a topic
POST_MEMORY_SURFACING = "memory_surfacing"  # recalls a past owner moment
POST_AGENT_THOUGHT = "agent_thought"    # the agent's OWN voice, clearly labelled
GHOST_POST_TYPES = (
    POST_OWNERS_DAY,
    POST_WORLD_OPINION,
    POST_MEMORY_SURFACING,
    POST_AGENT_THOUGHT,
)

# Approval lifecycle.
APPROVAL_AUTO_POSTED = "auto_posted"      # live on the feed (autonomy default)
APPROVAL_PENDING_REVIEW = "pending_review"  # waiting on the owner
APPROVAL_REJECTED = "rejected"            # owner declined; never hits the feed
APPROVAL_STATUSES = (
    APPROVAL_AUTO_POSTED,
    APPROVAL_PENDING_REVIEW,
    APPROVAL_REJECTED,
)


class GhostPost(Base):
    __tablename__ = "ghost_posts"

    id = Column(String, primary_key=True, default=_uuid)
    # owner_id is the human; agent_id is the agent that spoke for them. Both are
    # carried so the digest query ("what did MY agent post") is a single index hit.
    owner_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False, index=True)
    post_type = Column(String, nullable=False, index=True)
    content = Column(Text, nullable=False)
    approval_status = Column(
        String, nullable=False, default=APPROVAL_AUTO_POSTED, index=True
    )
    # Set when the ghost post goes live — links to the public social.AgentPost row.
    agent_post_id = Column(String, ForeignKey("agent_posts.id"), nullable=True)
    generated_at = Column(DateTime, default=datetime.utcnow, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
