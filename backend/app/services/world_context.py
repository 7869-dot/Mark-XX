"""Layer 6 — WorldContext: anonymized platform-wide signal."""
from datetime import datetime, timedelta
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Agent, Task, AgentInteraction


def build_world_context(db: Session) -> str:
    week_ago = datetime.utcnow() - timedelta(days=7)
    day_ago = datetime.utcnow() - timedelta(days=1)

    total_agents = db.query(func.count(Agent.id)).scalar() or 0
    tasks_week = (
        db.query(Task.task_type, func.count(Task.id))
        .filter(Task.created_at >= week_ago)
        .group_by(Task.task_type)
        .order_by(func.count(Task.id).desc())
        .limit(3)
        .all()
    )
    trending = ", ".join(f"{tt} ({n})" for tt, n in tasks_week) or "no trends yet"

    new_agents = db.query(func.count(Agent.id)).filter(Agent.created_at >= week_ago).scalar() or 0
    interactions_today = (
        db.query(func.count(AgentInteraction.id)).filter(AgentInteraction.created_at >= day_ago).scalar() or 0
    )

    return (
        f"Platform now has {total_agents} active agents ({new_agents} new this week). "
        f"Trending task types: {trending}. {interactions_today} agent-to-agent interactions in the last 24h."
    )
