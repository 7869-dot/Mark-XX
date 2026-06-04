"""Keeps agents.interest_tags / agents.goals in sync with their source data."""
from sqlalchemy.orm import Session

from app.models import Agent, UserPersonality
from app.core.logging import get_logger

logger = get_logger("axolot.profile_sync")


def _normalize_goals(raw) -> list:
    """users.goals is a list of strings; promote to {title, description, horizon}."""
    out = []
    for g in raw or []:
        if isinstance(g, dict):
            out.append({
                "title": g.get("title") or g.get("description") or "",
                "description": g.get("description") or g.get("title") or "",
                "horizon": g.get("horizon", "month"),
            })
        else:
            s = str(g)
            out.append({"title": s, "description": s, "horizon": "month"})
    return [g for g in out if g["title"]]


def sync_agent_profile(db: Session, agent: Agent, commit: bool = True) -> None:
    """Pull interest_tags from user_personalities and goals from users -> agent."""
    personality = (
        db.query(UserPersonality)
        .filter(UserPersonality.user_id == agent.user_id)
        .first()
    )
    if personality and personality.interests:
        agent.interest_tags = list(personality.interests)
    elif agent.interest_tags is None:
        agent.interest_tags = []

    user_goals = agent.user.goals if agent.user else []
    agent.goals = _normalize_goals(user_goals)
    if commit:
        db.commit()
