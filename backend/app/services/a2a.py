"""Agent-to-agent discovery, messaging, and compatibility scoring."""
import math
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models import Agent, AgentInteraction, UserPersonality
from app.models.interaction import InteractionStatus, InteractionType
from app.prompts.templates import A2A_INTRODUCTION, A2A_RESPONSE
from app.services.gemini import generate
from app.core.logging import get_logger, log_event

logger = get_logger("axolot.a2a")
PERSONALITY_KEYS = ["openness", "directness", "ambition", "sociability", "risk_tolerance"]
DAILY_INITIATION_LIMIT = 3


def initiations_today(db: Session, agent: Agent) -> int:
    day_ago = datetime.utcnow() - timedelta(days=1)
    return db.query(AgentInteraction).filter(
        AgentInteraction.initiator_agent_id == agent.id,
        AgentInteraction.created_at >= day_ago,
    ).count()


def can_initiate(db: Session, agent: Agent) -> bool:
    return initiations_today(db, agent) < DAILY_INITIATION_LIMIT


def cosine_similarity(a: dict, b: dict) -> float:
    av = [a.get(k, 0.5) for k in PERSONALITY_KEYS]
    bv = [b.get(k, 0.5) for k in PERSONALITY_KEYS]
    dot = sum(x * y for x, y in zip(av, bv))
    na = math.sqrt(sum(x * x for x in av))
    nb = math.sqrt(sum(x * x for x in bv))
    if na == 0 or nb == 0:
        return 0.0
    return dot / (na * nb)


def shared_interest_score(db: Session, agent_a: Agent, agent_b: Agent) -> float:
    pa = db.query(UserPersonality).filter(UserPersonality.user_id == agent_a.user_id).first()
    pb = db.query(UserPersonality).filter(UserPersonality.user_id == agent_b.user_id).first()
    if not pa or not pb:
        return 0.0
    ia = set(pa.interests or [])
    ib = set(pb.interests or [])
    if not ia or not ib:
        return 0.0
    return len(ia & ib) / max(len(ia | ib), 1)


def compatibility(db: Session, agent_a: Agent, agent_b: Agent) -> float:
    """0..100 score weighting personality similarity and interest overlap."""
    p = cosine_similarity(agent_a.personality_vector or {}, agent_b.personality_vector or {})
    s = shared_interest_score(db, agent_a, agent_b)
    raw = 0.7 * p + 0.3 * s
    return round(raw * 100, 1)


def discover_compatible(db: Session, agent: Agent, limit: int = 10) -> list[tuple[Agent, float]]:
    others = db.query(Agent).filter(Agent.id != agent.id).all()
    scored = [(o, compatibility(db, agent, o)) for o in others]
    scored.sort(key=lambda x: (x[1], x[0].reputation_score or 0), reverse=True)
    return scored[:limit]


def initiate_interaction(
    db: Session,
    initiator: Agent,
    target: Agent,
    interaction_type: InteractionType = InteractionType.introduction,
    message: str | None = None,
) -> AgentInteraction:
    compat = compatibility(db, initiator, target)

    if not message:
        target_profile = f"Agent of {target.user.name}. Reputation {target.reputation_score:.0f}."
        prompt = A2A_INTRODUCTION.format(
            initiator_agent_name=initiator.name,
            initiator_user_name=initiator.user.name,
            initiator_personality=initiator.personality_vector,
            initiator_goals=initiator.user.goals or [],
            target_agent_name=target.name,
            target_user_name=target.user.name,
            target_profile=target_profile,
            compatibility_score=compat,
        )
        message = generate(prompt, response_format="intro")

    interaction = AgentInteraction(
        initiator_agent_id=initiator.id,
        target_agent_id=target.id,
        interaction_type=interaction_type,
        message=message,
        status=InteractionStatus.sent,
        compatibility_score=compat,
        last_contacted_at=datetime.utcnow(),
    )
    db.add(interaction)
    db.commit()
    db.refresh(interaction)
    log_event(
        logger, "a2a_initiated",
        interaction_id=interaction.id,
        initiator=initiator.id,
        target=target.id,
        compat=compat,
    )

    # Auto-generate response from the target agent (the target user's agent answers).
    response_prompt = A2A_RESPONSE.format(
        target_agent_name=target.name,
        target_user_name=target.user.name,
        target_personality=target.personality_vector,
        target_goals=target.user.goals or [],
        initiator_agent_name=initiator.name,
        initiator_user_name=initiator.user.name,
        incoming_message=message,
    )
    response_text = generate(response_prompt, response_format="response")
    interaction.response = response_text
    interaction.status = InteractionStatus.responded
    interaction.responded_at = datetime.utcnow()
    db.commit()
    db.refresh(interaction)
    return interaction


def _upsert_edge(agent: Agent, other_id: str, relationship_type: str) -> None:
    graph = list(agent.social_graph or [])
    for edge in graph:
        if edge.get("agent_id") == other_id:
            edge["interaction_count"] = edge.get("interaction_count", 1) + 1
            agent.social_graph = graph
            return
    graph.append({
        "agent_id": other_id,
        "relationship_type": relationship_type,
        "connected_at": datetime.utcnow().isoformat(),
        "interaction_count": 1,
    })
    agent.social_graph = graph


def accept_interaction(db: Session, interaction: AgentInteraction, relationship_type: str = "collaborator") -> None:
    """Move an interaction to accepted and persist a bidirectional social edge."""
    from app.services.reputation import record_event

    interaction.status = InteractionStatus.accepted
    initiator = db.query(Agent).filter(Agent.id == interaction.initiator_agent_id).first()
    target = db.query(Agent).filter(Agent.id == interaction.target_agent_id).first()
    if initiator and target:
        _upsert_edge(initiator, target.id, relationship_type)
        _upsert_edge(target, initiator.id, relationship_type)
        record_event(db, initiator, "interaction_accepted", reason=f"interaction {interaction.id}")
        record_event(db, target, "interaction_accepted", reason=f"interaction {interaction.id}")
    db.commit()
    log_event(logger, "a2a_accepted", interaction_id=interaction.id)


def decline_interaction(db: Session, interaction: AgentInteraction) -> None:
    from app.services.reputation import record_event

    interaction.status = InteractionStatus.declined
    initiator = db.query(Agent).filter(Agent.id == interaction.initiator_agent_id).first()
    if initiator:
        record_event(db, initiator, "interaction_declined", reason=f"interaction {interaction.id}")
    db.commit()
    log_event(logger, "a2a_declined", interaction_id=interaction.id)
