"""End-to-end A2A interaction: compatibility -> message -> response -> persistence."""
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models import Agent, AgentInteraction, AgentDiscoveryLog
from app.models.interaction import InteractionType, InteractionStatus, ConnectionType
from app.services.compatibility import compute_compatibility
from app.services.a2a_messaging import generate_introduction, generate_response
from app.services.profile_sync import upsert_connection
from app.core.logging import get_logger, log_event

logger = get_logger("axolot.a2a_engine")


def already_connected(db: Session, a_id: str, b_id: str) -> bool:
    from app.models import AgentConnection

    lo, hi = (a_id, b_id) if a_id < b_id else (b_id, a_id)
    return (
        db.query(AgentConnection)
        .filter(AgentConnection.agent_a_id == lo, AgentConnection.agent_b_id == hi)
        .first()
        is not None
    )


def recently_discovered(db: Session, agent_id: str, other_id: str, days: int = 7) -> bool:
    cutoff = datetime.utcnow() - timedelta(days=days)
    return (
        db.query(AgentDiscoveryLog)
        .filter(
            AgentDiscoveryLog.agent_id == agent_id,
            AgentDiscoveryLog.discovered_agent_id == other_id,
            AgentDiscoveryLog.discovered_at >= cutoff,
        )
        .first()
        is not None
    )


def log_discovery(
    db: Session, agent_id: str, other_id: str, score: float, reason: str,
    acted_on: bool = False, commit: bool = True,
) -> None:
    db.add(AgentDiscoveryLog(
        agent_id=agent_id,
        discovered_agent_id=other_id,
        compatibility_score=score,
        reason=reason,
        was_acted_on=acted_on,
        discovered_at=datetime.utcnow(),
    ))
    if commit:
        db.commit()


def run_interaction(
    db: Session,
    initiator: Agent,
    target: Agent,
    interaction_type: InteractionType = InteractionType.introduction,
    custom_message: str | None = None,
) -> tuple[AgentInteraction, dict]:
    """Compute compatibility, generate the full two-sided exchange, persist everything."""
    compat = compute_compatibility(initiator, target)

    intro = custom_message or generate_introduction(initiator, target, compat)
    response = generate_response(target, initiator, intro, compat)

    interaction = AgentInteraction(
        initiator_agent_id=initiator.id,
        target_agent_id=target.id,
        interaction_type=interaction_type,
        message=intro,                 # legacy column
        response=response,             # legacy column
        initiator_message=intro,       # spec column
        target_response=response,      # spec column
        shared_goals=compat.get("shared_goals", []),
        status=InteractionStatus.responded,
        compatibility_score=compat["score"],
        last_contacted_at=datetime.utcnow(),
        responded_at=datetime.utcnow(),
        human_a_notified=False,
        human_b_notified=False,
    )
    db.add(interaction)

    initiator.total_interactions = (initiator.total_interactions or 0) + 1
    target.total_interactions = (target.total_interactions or 0) + 1

    upsert_connection(
        db, initiator.id, target.id,
        compatibility_score=compat["score"],
        connection_type=ConnectionType.discovered,
        initiated_by=initiator.id,
        commit=False,
    )
    db.commit()
    db.refresh(interaction)

    log_discovery(
        db, initiator.id, target.id, compat["score"], compat["reason"],
        acted_on=True,
    )
    log_event(
        logger, "a2a_interaction",
        interaction_id=interaction.id,
        initiator=initiator.id,
        target=target.id,
        score=compat["score"],
    )
    return interaction, compat
