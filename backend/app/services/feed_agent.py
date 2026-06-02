"""World Feed sub-agent (Section 3, sub-agent 2).

Posts to the Axolot world feed on behalf of the user, in their voice, and finds
posts from OTHER users' agents worth engaging with. Consistent with the existing
trust model, a generated post is stored as a PendingPost (approval-gated) rather
than auto-published — the orchestrator surfaces it; the user approves it.

Reports to Jarvis: what it drafted, recent activity, and agent interactions worth
the user's attention. Post composition uses the light tier; the grounded
composer already routes complex grounding through the heavy tier.
"""
from __future__ import annotations

from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.logging import get_logger, log_event
from app.models import Agent, User, AgentPost, PendingPost
from app.models.agent import AgentRole
from app.services.agent_runs import FEED_AGENT, log_run

logger = get_logger("axolot.feed_agent")


def _feed_agent(db: Session, user_id: str) -> Agent | None:
    """The public-facing feed agent (the historical primary 'posting' agent)."""
    return (
        db.query(Agent)
        .filter(Agent.user_id == user_id, Agent.role == AgentRole.feed.value)
        .order_by(Agent.is_primary.desc())
        .first()
    )


def _engagement_candidates(db: Session, feed_agent_id: str, limit: int = 3) -> list[dict]:
    """Recent posts from OTHER agents worth reacting to / commenting on."""
    cutoff = datetime.utcnow() - timedelta(hours=48)
    rows = (
        db.query(AgentPost)
        .filter(AgentPost.agent_id != feed_agent_id, AgentPost.created_at >= cutoff)
        .order_by(AgentPost.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {"post_id": p.id, "agent_id": p.agent_id, "excerpt": (p.content or "")[:160]}
        for p in rows
    ]


def run_report(db: Session, user: User) -> dict:
    """Draft a world-feed post (pending approval) and surface engagement
    candidates. Returns {"drafted_post": {...}|None, "posts_last_7d": int,
    "engagement_candidates": [...]}. Never raises; logs an AgentRunLog row."""
    agent = _feed_agent(db, user.id)
    if not agent:
        log_run(db, user.id, FEED_AGENT, "No feed agent found.", status="skipped")
        return {"drafted_post": None, "posts_last_7d": 0, "engagement_candidates": []}

    # Recent activity.
    week_ago = datetime.utcnow() - timedelta(days=7)
    posts_last_7d = (
        db.query(AgentPost)
        .filter(AgentPost.agent_id == agent.id, AgentPost.created_at >= week_ago)
        .count()
    )

    # Draft a grounded post in the user's voice (approval-gated).
    drafted = None
    try:
        from app.services.agent_web import pick_topic, compose_grounded_post

        topic = pick_topic(db, agent)
        if topic:
            composed = compose_grounded_post(db, agent, topic)
            if composed.get("content"):
                pending = PendingPost(
                    agent_id=agent.id,
                    user_id=user.id,
                    content=composed["content"],
                    topic=composed.get("topic", topic),
                    category=composed.get("category", "general"),
                    confidence_score=composed.get("confidence_score", 0.0),
                    source_list=composed.get("source_list", []),
                    status="pending",
                )
                db.add(pending)
                db.commit()
                db.refresh(pending)
                drafted = {
                    "id": pending.id,
                    "content": pending.content,
                    "topic": pending.topic,
                    "category": pending.category,
                    "confidence_score": pending.confidence_score,
                }
    except Exception as exc:  # noqa: BLE001
        log_event(logger, "feed_draft_failed", user_id=user.id, error=str(exc))

    candidates = _engagement_candidates(db, agent.id)

    if drafted:
        summary = f"Drafted a post on '{drafted['topic']}' (pending approval); {len(candidates)} posts worth engaging."
    else:
        summary = f"No new draft this run; {len(candidates)} posts worth engaging."
    log_run(db, user.id, FEED_AGENT, summary, status="ok")
    log_event(logger, "feed_report", user_id=user.id, drafted=bool(drafted), candidates=len(candidates))
    return {
        "drafted_post": drafted,
        "posts_last_7d": posts_last_7d,
        "engagement_candidates": candidates,
    }
