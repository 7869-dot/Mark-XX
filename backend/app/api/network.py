from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.db import get_db
from app.core.security import get_current_user
from app.core.cache import cache
from app.core.ratelimit import limiter
from app.models import User, Agent, AgentInteraction, UserPersonality
from app.models.interaction import InteractionType
from app.schemas.interaction import InteractionCreate
from app.api.envelope import envelope
from app.prompts.templates import AGENT_BIO
from app.services.gemini import generate
from app.services.a2a import (
    discover_compatible,
    initiate_interaction,
    compatibility,
    can_initiate,
    accept_interaction,
    DAILY_INITIATION_LIMIT,
)


router = APIRouter(prefix="/agents", tags=["network"])


def _public_profile(db: Session, agent: Agent, compat: float | None = None, bio: bool = False) -> dict:
    personality = db.query(UserPersonality).filter(UserPersonality.user_id == agent.user_id).first()
    data = {
        "id": agent.id,
        "name": agent.name,
        "user_name": agent.user.name if agent.user else "",
        "reputation_score": agent.reputation_score,
        "personality_vector": agent.personality_vector or {},
        "total_tasks_completed": agent.total_tasks_completed,
        "status": agent.status.value if hasattr(agent.status, "value") else agent.status,
        "avatar_seed": agent.avatar_seed,
        "interests": (personality.interests if personality else []) or [],
        "social_graph_size": len(agent.social_graph or []),
        "compatibility_score": compat,
    }
    if bio:
        key = f"bio:{agent.id}"
        cached = cache.get(key)
        if cached is None:
            cached = generate(
                AGENT_BIO.format(
                    personality_vector=agent.personality_vector or {},
                    goals=(agent.user.goals if agent.user else []) or [],
                ),
                response_format="bio",
            )
            cache.set(key, cached, ttl_seconds=1800)  # 30 min per agent
        data["bio"] = cached
    return data


@router.get("/discover")
def discover(limit: int = 10, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user.agent:
        raise HTTPException(status_code=404, detail="No agent")
    key = f"discover:{user.agent.id}:{limit}"
    cached = cache.get(key)
    if cached is not None:
        return envelope(cached, agent_id=user.agent.id)
    matches = discover_compatible(db, user.agent, limit=limit)
    data = [_public_profile(db, a, compat=score) for a, score in matches]
    cache.set(key, data, ttl_seconds=3600)  # 1 hour per user
    return envelope(data, agent_id=user.agent.id)


@router.get("/connections")
def connections(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user.agent:
        raise HTTPException(status_code=404, detail="No agent")
    graph = user.agent.social_graph or []
    ids = [c.get("agent_id") for c in graph if c.get("agent_id")]
    if not ids:
        return envelope([], agent_id=user.agent.id)
    agents = db.query(Agent).filter(Agent.id.in_(ids)).all()
    return envelope(
        [_public_profile(db, a, compat=compatibility(db, user.agent, a)) for a in agents],
        agent_id=user.agent.id,
    )


@router.post("/interact")
@limiter.limit("5/minute")
def interact(
    request: Request,
    payload: InteractionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not user.agent:
        raise HTTPException(status_code=404, detail="No agent")
    target = db.query(Agent).filter(Agent.id == payload.target_agent_id).first()
    if not target or target.id == user.agent.id:
        raise HTTPException(status_code=404, detail="Target agent not found")
    # Daily A2A cap enforced at the API layer, not just the scheduler.
    if not can_initiate(db, user.agent):
        raise HTTPException(
            status_code=429,
            detail=(
                f"Your agent has reached its daily connection limit "
                f"({DAILY_INITIATION_LIMIT}). It will be able to reach out again tomorrow."
            ),
        )
    try:
        itype = InteractionType(payload.interaction_type)
    except ValueError:
        itype = InteractionType.introduction
    interaction = initiate_interaction(db, user.agent, target, itype, payload.message)
    cache.invalidate(f"discover:{user.agent.id}:10")
    return envelope({
        "id": interaction.id,
        "initiator_agent_id": interaction.initiator_agent_id,
        "target_agent_id": interaction.target_agent_id,
        "interaction_type": interaction.interaction_type.value,
        "message": interaction.message,
        "response": interaction.response,
        "status": interaction.status.value,
        "compatibility_score": interaction.compatibility_score,
        "created_at": interaction.created_at.isoformat(),
        "responded_at": interaction.responded_at.isoformat() if interaction.responded_at else None,
    }, agent_id=user.agent.id)


@router.get("/interactions")
def interactions(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user.agent:
        raise HTTPException(status_code=404, detail="No agent")
    items = (
        db.query(AgentInteraction)
        .filter(or_(
            AgentInteraction.initiator_agent_id == user.agent.id,
            AgentInteraction.target_agent_id == user.agent.id,
        ))
        .order_by(AgentInteraction.created_at.desc())
        .all()
    )
    out = []
    for i in items:
        outbound = i.initiator_agent_id == user.agent.id
        other_id = i.target_agent_id if outbound else i.initiator_agent_id
        other = db.query(Agent).filter(Agent.id == other_id).first()
        out.append({
            "id": i.id,
            "outbound": outbound,
            "other_agent": _public_profile(db, other) if other else None,
            "interaction_type": i.interaction_type.value,
            "message": i.message,
            "response": i.response,
            "status": i.status.value,
            "compatibility_score": i.compatibility_score,
            "created_at": i.created_at.isoformat(),
            "responded_at": i.responded_at.isoformat() if i.responded_at else None,
        })
    return envelope(out, agent_id=user.agent.id)


@router.get("/{agent_id}/profile")
def public_profile(agent_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    a = db.query(Agent).filter(Agent.id == agent_id).first()
    if not a:
        raise HTTPException(status_code=404, detail="Agent not found")
    compat = compatibility(db, user.agent, a) if user.agent else None
    return envelope(
        _public_profile(db, a, compat=compat, bio=True),
        agent_id=user.agent.id if user.agent else None,
    )


@router.post("/interactions/{interaction_id}/human-followup")
def human_followup(interaction_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    i = db.query(AgentInteraction).filter(AgentInteraction.id == interaction_id).first()
    if not i:
        raise HTTPException(status_code=404, detail="Interaction not found")
    if user.agent.id not in (i.initiator_agent_id, i.target_agent_id):
        raise HTTPException(status_code=403, detail="Not your interaction")
    accept_interaction(db, i, relationship_type="collaborator")
    other_id = i.target_agent_id if i.initiator_agent_id == user.agent.id else i.initiator_agent_id
    return envelope({"ok": True, "connected_to": other_id}, agent_id=user.agent.id)
