"""Keeps agents.interest_tags / agents.goals in sync with their source data,
and performs the one-time social_graph -> agent_connections cut-over.
"""
from datetime import datetime
from sqlalchemy.orm import Session

from app.models import Agent, UserPersonality, AgentConnection
from app.models.interaction import ConnectionType
from app.core.logging import get_logger, log_event

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


def _ordered(a_id: str, b_id: str) -> tuple[str, str]:
    return (a_id, b_id) if a_id < b_id else (b_id, a_id)


def upsert_connection(
    db: Session,
    agent_a_id: str,
    agent_b_id: str,
    compatibility_score: float,
    connection_type: ConnectionType = ConnectionType.discovered,
    initiated_by: str | None = None,
    commit: bool = True,
) -> AgentConnection:
    a_id, b_id = _ordered(agent_a_id, agent_b_id)
    conn = (
        db.query(AgentConnection)
        .filter(AgentConnection.agent_a_id == a_id, AgentConnection.agent_b_id == b_id)
        .first()
    )
    if conn:
        conn.interaction_count = (conn.interaction_count or 1) + 1
        conn.compatibility_score = compatibility_score
        # only "upgrade" the relationship strength
        order = ["discovered", "following", "introduced", "collaborated"]
        cur = conn.connection_type.value if hasattr(conn.connection_type, "value") else conn.connection_type
        if order.index(connection_type.value) > order.index(cur or "discovered"):
            conn.connection_type = connection_type
    else:
        conn = AgentConnection(
            agent_a_id=a_id,
            agent_b_id=b_id,
            compatibility_score=compatibility_score,
            connection_type=connection_type,
            initiated_by=initiated_by,
            interaction_count=1,
            created_at=datetime.utcnow(),
        )
        db.add(conn)
    if commit:
        db.commit()
    return conn


def migrate_social_graph_to_connections(db: Session) -> int:
    """One-time idempotent cut-over of legacy agents.social_graph edges."""
    migrated = 0
    for agent in db.query(Agent).all():
        for edge in agent.social_graph or []:
            other = edge.get("agent_id")
            if not other:
                continue
            a_id, b_id = _ordered(agent.id, other)
            exists = (
                db.query(AgentConnection)
                .filter(
                    AgentConnection.agent_a_id == a_id,
                    AgentConnection.agent_b_id == b_id,
                )
                .first()
            )
            if exists:
                continue
            db.add(
                AgentConnection(
                    agent_a_id=a_id,
                    agent_b_id=b_id,
                    compatibility_score=0.0,
                    connection_type=ConnectionType.introduced,
                    interaction_count=edge.get("interaction_count", 1),
                    created_at=datetime.utcnow(),
                )
            )
            migrated += 1
    if migrated:
        db.commit()
        log_event(logger, "social_graph_migrated", edges=migrated)
    return migrated
