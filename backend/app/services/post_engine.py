"""World-Aware Post Engine.

Combines [live event data] + [user's interests/opinions] + [user's voice] into
a grounded draft, then routes it by the user's per-category trust level:

  MANUAL — draft lands in the pending queue; owner approves/edits/rejects.
  SEMI   — agent publishes, owner is notified.
  AUTO   — agent publishes fully autonomously.

Never auto-publishes below the confidence threshold or for a sensitive category.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger, log_event
from app.models import (
    Agent, AgentPost, NotificationType, PendingPost, TrustSetting,
    TRUST_MANUAL, TRUST_SEMI, TRUST_AUTO, SENSITIVE_CATEGORIES,
)
from app.models.agent import AgentMemory, AgentMemoryType
from app.services import agent_web, notifications
from app.services.activity_logger import log_activity
from app.models import ActivityType

logger = get_logger("axolot.post_engine")


# ── Trust settings ───────────────────────────────────────────────────────────
def get_trust(db: Session, user_id: str, category: str) -> str:
    row = (
        db.query(TrustSetting)
        .filter(TrustSetting.user_id == user_id, TrustSetting.category == category)
        .first()
    )
    return row.level if row else TRUST_MANUAL


def set_trust(db: Session, user_id: str, category: str, level: str) -> TrustSetting:
    row = (
        db.query(TrustSetting)
        .filter(TrustSetting.user_id == user_id, TrustSetting.category == category)
        .first()
    )
    if row:
        row.level = level
    else:
        row = TrustSetting(user_id=user_id, category=category, level=level)
        db.add(row)
    db.commit()
    db.refresh(row)
    return row


def all_trust(db: Session, user_id: str) -> dict[str, str]:
    from app.models.web import TOPIC_CATEGORIES

    rows = {r.category: r.level for r in db.query(TrustSetting).filter(TrustSetting.user_id == user_id).all()}
    return {cat: rows.get(cat, TRUST_MANUAL) for cat in TOPIC_CATEGORIES}


# ── Publish ──────────────────────────────────────────────────────────────────
# Separation of concerns (Sprint 3A): the world-post engine operates only on
# PendingPost → AgentPost. It NEVER reads jarvis post_drafts; those are a
# separate queue that reaches the feed only via the posting agent's approval.
def _publish(db: Session, agent: Agent, pending: PendingPost) -> AgentPost:
    post = AgentPost(
        agent_id=agent.id,
        content=pending.content[:500],
        post_type="world",
        is_agent_post=True,
    )
    db.add(post)
    db.add(AgentMemory(
        agent_id=agent.id, memory_type=AgentMemoryType.post_history,
        content=f"[world:{pending.topic}] {pending.content[:240]}", importance_score=0.5,
    ))
    pending.status = "published"
    pending.decided_at = datetime.utcnow()
    db.commit()
    db.refresh(post)
    pending.agent_post_id = post.id
    db.commit()
    log_activity(
        db, agent.id, ActivityType.other,
        f"{agent.name} posted about {pending.topic}.",
        metadata={"post_id": post.id, "topic": pending.topic, "confidence": pending.confidence_score},
    )
    if agent.user_id:
        notifications.notify_agent_post(db, agent.user_id, pending.content)
    log_event(logger, "world_post_published", agent_id=agent.id, post_id=post.id, topic=pending.topic)
    return post


def approve_pending(db: Session, agent: Agent, pending: PendingPost) -> AgentPost:
    return _publish(db, agent, pending)


def reject_pending(db: Session, pending: PendingPost) -> None:
    pending.status = "rejected"
    pending.decided_at = datetime.utcnow()
    db.commit()


# ── Draft ────────────────────────────────────────────────────────────────────
def draft_world_post(db: Session, agent: Agent, topic: str | None = None) -> dict | None:
    """Produce one grounded draft and route it by trust. Returns a summary dict
    ({pending_id, status, published, confidence, topic, sources}) or None."""
    if not agent.user_id:
        return None
    topic = topic or agent_web.pick_topic(db, agent)
    if not topic:
        return None

    composed = agent_web.compose_grounded_post(db, agent, topic)
    if not composed["content"]:
        return None

    category = composed["category"]
    confidence = composed["confidence_score"]
    sensitive = category in SENSITIVE_CATEGORIES
    level = get_trust(db, agent.user_id, category)

    pending = PendingPost(
        agent_id=agent.id,
        user_id=agent.user_id,
        content=composed["content"],
        topic=topic,
        category=category,
        confidence_score=confidence,
        source_list=composed["source_list"],
        status="pending",
    )
    db.add(pending)
    db.commit()
    db.refresh(pending)

    # Reinforce the topic the agent chose to engage.
    agent_web.upsert_topic(db, agent.user_id, topic, source="inferred", delta=0.2)

    can_auto = (
        confidence >= settings.POST_CONFIDENCE_THRESHOLD
        and not sensitive
        and level in (TRUST_SEMI, TRUST_AUTO)
    )
    published = False
    if can_auto:
        _publish(db, agent, pending)
        published = True
        if level == TRUST_SEMI and agent.user_id:
            notifications.notify(
                db, agent.user_id, NotificationType.AGENT_POST,
                "Your agent posted (you can review it)",
                f"On {topic} — “{composed['content'][:80]}”", link="/world",
            )
    else:
        # Pending — tell the owner there's something to approve, and why it held.
        why = (
            "sensitive topic" if sensitive
            else "low confidence" if confidence < settings.POST_CONFIDENCE_THRESHOLD
            else "manual approval on"
        )
        if agent.user_id:
            notifications.notify(
                db, agent.user_id, NotificationType.AGENT_POST,
                f"Your agent drafted a post about {topic}",
                f"Held for your approval ({why}). “{composed['content'][:70]}”",
                link="/world",
            )

    return {
        "pending_id": pending.id,
        "status": pending.status,
        "published": published,
        "confidence": confidence,
        "topic": topic,
        "category": category,
        "sources": composed["source_list"],
        "content": composed["content"],
    }
