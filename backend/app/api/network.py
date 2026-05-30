"""A2A network router.

Per the build decision, NEW routes use the spec error envelope
{ success:false, error:{ code, message } }. Success stays
{ success:true, data, meta:{ timestamp, agent_id } }.
"""
from datetime import datetime
from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse
from sqlalchemy.orm import Session
from sqlalchemy import or_, func

from app.core.db import get_db
from app.core.security import get_current_user
from app.core.cache import cache
from app.core.ratelimit import limiter
from app.models import (
    User,
    Agent,
    AgentInteraction,
    AgentConnection,
    AgentDiscoveryLog,
    UserPersonality,
)
from app.services import a2a_recommendations
from app.models.interaction import InteractionType, InteractionStatus
from app.schemas.interaction import InteractionCreate
from app.prompts.templates import AGENT_BIO
from app.services.gemini import generate
from app.services.compatibility import compute_compatibility
from app.services.a2a import can_initiate, DAILY_INITIATION_LIMIT
from app.services.a2a_engine import run_interaction, already_connected
from app.services.a2a_messaging import generate_human_summary
from app.services.profile_sync import sync_agent_profile

router = APIRouter(tags=["network"])


def _meta(agent_id: str | None) -> dict:
    return {"timestamp": datetime.utcnow().isoformat(), "agent_id": agent_id}


def ok(data, agent_id: str | None = None):
    return {"success": True, "data": data, "meta": _meta(agent_id)}


def fail(code: str, message: str, status: int = 400):
    return JSONResponse(
        status_code=status,
        content={"success": False, "error": {"code": code, "message": message}},
    )


def _public_profile(db: Session, agent: Agent, compat: float | None = None, bio: bool = False) -> dict:
    """Public-safe — NEVER includes personality_vector."""
    data = {
        "id": agent.id,
        "name": agent.name,
        "user_name": agent.user.name if agent.user else "",
        "reputation_score": agent.reputation_score,
        "interest_tags": agent.interest_tags or [],
        "goals": [g for g in (agent.goals or [])],
        "total_interactions": agent.total_interactions or 0,
        "status": agent.status.value if hasattr(agent.status, "value") else agent.status,
        "avatar_seed": agent.avatar_seed,
        "created_at": agent.created_at.isoformat() if agent.created_at else None,
        "compatibility_score": compat,
    }
    if bio:
        key = f"bio:{agent.id}"
        cached = cache.get(key)
        if cached is None:
            cached = generate(
                AGENT_BIO.format(
                    personality_vector=agent.personality_vector or {},
                    goals=agent.goal_titles,
                ),
                response_format="bio",
            )
            cache.set(key, cached, ttl_seconds=1800)
        data["bio"] = cached
    return data


def _summary_for(db: Session, i: AgentInteraction) -> str:
    key = f"a2a_summary:{i.id}"
    cached = cache.get(key)
    if cached is not None:
        return cached
    initiator = db.query(Agent).filter(Agent.id == i.initiator_agent_id).first()
    target = db.query(Agent).filter(Agent.id == i.target_agent_id).first()
    summary = generate_human_summary(i, initiator, target) if initiator and target else ""
    cache.set(key, summary, ttl_seconds=1800)
    return summary


def _interaction_dict(db: Session, i: AgentInteraction, viewer_agent_id: str) -> dict:
    outbound = i.initiator_agent_id == viewer_agent_id
    other_id = i.target_agent_id if outbound else i.initiator_agent_id
    other = db.query(Agent).filter(Agent.id == other_id).first()
    return {
        "id": i.id,
        "outbound": outbound,
        "interaction_type": i.interaction_type.value if hasattr(i.interaction_type, "value") else i.interaction_type,
        "initiator_message": i.initiator_message or i.message,
        "target_response": i.target_response or i.response,
        "message": i.message,
        "response": i.response,
        "shared_goals": i.shared_goals or [],
        "compatibility_score": i.compatibility_score,
        "status": i.status.value if hasattr(i.status, "value") else i.status,
        "human_summary": _summary_for(db, i),
        "other_agent": _public_profile(db, other) if other else None,
        "created_at": i.created_at.isoformat() if i.created_at else None,
        "responded_at": i.responded_at.isoformat() if i.responded_at else None,
    }


# ── Discovery ──────────────────────────────────────────────────────────────
@router.get("/agents/discover")
def discover(limit: int = 10, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user.agent:
        return fail("AGENT_NOT_FOUND", "You have no agent yet", 404)
    me = user.agent
    sync_agent_profile(db, me)

    cache_key = f"discover_rich:{me.id}:{limit}"
    cached = cache.get(cache_key)
    if cached is not None:
        return ok(cached, me.id)

    results = []
    for other in db.query(Agent).filter(Agent.id != me.id).all():
        if other.user_id == me.user_id:
            continue
        if already_connected(db, me.id, other.id):
            continue
        compat = compute_compatibility(me, other)
        results.append({
            "agent": _public_profile(db, other),
            "user_name": other.user.name if other.user else "",
            "compatibility_score": compat["score"],
            "breakdown": compat["breakdown"],
            "shared_goals": compat["shared_goals"],
            "reason": compat["reason"],
            # convenience top-level fields
            "id": other.id,
            "name": other.name,
        })
    results.sort(key=lambda r: r["compatibility_score"], reverse=True)
    top = results[:limit]
    cache.set(cache_key, top, ttl_seconds=3600)
    return ok(top, me.id)


# ── Connections ────────────────────────────────────────────────────────────
@router.get("/agents/connections")
def connections(
    connection_type: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not user.agent:
        return fail("AGENT_NOT_FOUND", "You have no agent yet", 404)
    me = user.agent
    q = db.query(AgentConnection).filter(
        or_(AgentConnection.agent_a_id == me.id, AgentConnection.agent_b_id == me.id)
    )
    if connection_type:
        q = q.filter(AgentConnection.connection_type == connection_type)
    out = []
    for c in q.order_by(AgentConnection.created_at.desc()).all():
        other_id = c.agent_b_id if c.agent_a_id == me.id else c.agent_a_id
        other = db.query(Agent).filter(Agent.id == other_id).first()
        if not other:
            continue
        out.append({
            "connection_id": c.id,
            "connection_type": c.connection_type.value if hasattr(c.connection_type, "value") else c.connection_type,
            "compatibility_score": c.compatibility_score,
            "human_followed_up": c.human_followed_up,
            "interaction_count": c.interaction_count,
            "created_at": c.created_at.isoformat() if c.created_at else None,
            "agent": _public_profile(db, other),
        })
    return ok(out, me.id)


# ── Interactions list + feed ───────────────────────────────────────────────
@router.get("/agents/interactions/feed")
def interactions_feed(
    limit: int = 20,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not user.agent:
        return fail("AGENT_NOT_FOUND", "You have no agent yet", 404)
    me = user.agent
    items = (
        db.query(AgentInteraction)
        .filter(or_(
            AgentInteraction.initiator_agent_id == me.id,
            AgentInteraction.target_agent_id == me.id,
        ))
        .order_by(AgentInteraction.created_at.desc())
        .offset(offset)
        .limit(limit)
        .all()
    )
    return ok(
        {
            "items": [_interaction_dict(db, i, me.id) for i in items],
            "next_offset": offset + len(items),
        },
        me.id,
    )


@router.get("/agents/interactions")
def interactions(
    status: str | None = None,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not user.agent:
        return fail("AGENT_NOT_FOUND", "You have no agent yet", 404)
    me = user.agent
    q = db.query(AgentInteraction).filter(
        or_(
            AgentInteraction.initiator_agent_id == me.id,
            AgentInteraction.target_agent_id == me.id,
        )
    )
    if status:
        q = q.filter(AgentInteraction.status == status)
    items = q.order_by(AgentInteraction.created_at.desc()).all()
    return ok([_interaction_dict(db, i, me.id) for i in items], me.id)


# ── Initiate ───────────────────────────────────────────────────────────────
@router.post("/agents/interact")
@limiter.limit("5/minute")
def interact(
    request: Request,
    payload: InteractionCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not user.agent:
        return fail("AGENT_NOT_FOUND", "You have no agent yet", 404)
    me = user.agent
    target = db.query(Agent).filter(Agent.id == payload.target_agent_id).first()
    if not target or target.id == me.id:
        return fail("TARGET_NOT_FOUND", "Target agent not found", 404)
    if not can_initiate(db, me):
        return fail(
            "DAILY_LIMIT_REACHED",
            f"Your agent has reached its daily connection limit "
            f"({DAILY_INITIATION_LIMIT}). It will be able to reach out again tomorrow.",
            429,
        )
    try:
        itype = InteractionType(payload.interaction_type)
    except ValueError:
        itype = InteractionType.introduction

    sync_agent_profile(db, me)
    sync_agent_profile(db, target)
    custom = payload.custom_message or payload.message
    interaction, compat = run_interaction(db, me, target, itype, custom)
    cache.invalidate(f"discover_rich:{me.id}:10")
    data = _interaction_dict(db, interaction, me.id)
    data["compatibility_breakdown"] = compat["breakdown"]
    return ok(data, me.id)


# ── Accept / Decline / Follow-up ───────────────────────────────────────────
def _load_interaction(db, interaction_id, me):
    i = db.query(AgentInteraction).filter(AgentInteraction.id == interaction_id).first()
    if not i:
        return None, fail("INTERACTION_NOT_FOUND", "Interaction not found", 404)
    if me.id not in (i.initiator_agent_id, i.target_agent_id):
        return None, fail("FORBIDDEN", "Not your interaction", 403)
    return i, None


@router.post("/agents/interactions/{interaction_id}/accept")
def accept(interaction_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user.agent:
        return fail("AGENT_NOT_FOUND", "You have no agent yet", 404)
    me = user.agent
    i, error = _load_interaction(db, interaction_id, me)
    if error:
        return error
    from app.services.a2a import accept_interaction

    accept_interaction(db, i, relationship_type="collaborator")
    if i.initiator_agent_id == me.id:
        i.human_a_notified = True
    else:
        i.human_b_notified = True
    db.commit()
    return ok({"status": "accepted", "interaction_id": i.id}, me.id)


@router.post("/agents/interactions/{interaction_id}/decline")
def decline(interaction_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user.agent:
        return fail("AGENT_NOT_FOUND", "You have no agent yet", 404)
    me = user.agent
    i, error = _load_interaction(db, interaction_id, me)
    if error:
        return error
    from app.services.a2a import decline_interaction

    decline_interaction(db, i)
    return ok({"status": "declined", "interaction_id": i.id}, me.id)


@router.post("/agents/interactions/{interaction_id}/human-followup")
def human_followup(interaction_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    if not user.agent:
        return fail("AGENT_NOT_FOUND", "You have no agent yet", 404)
    me = user.agent
    i, error = _load_interaction(db, interaction_id, me)
    if error:
        return error
    other_id = i.target_agent_id if i.initiator_agent_id == me.id else i.initiator_agent_id
    other = db.query(Agent).filter(Agent.id == other_id).first()

    lo, hi = (me.id, other_id) if me.id < other_id else (other_id, me.id)
    conn = (
        db.query(AgentConnection)
        .filter(AgentConnection.agent_a_id == lo, AgentConnection.agent_b_id == hi)
        .first()
    )
    if conn:
        conn.human_followed_up = True
    db.commit()
    return ok(
        {
            "ok": True,
            "other_user_name": other.user.name if other and other.user else None,
            "other_user_email": other.user.email if other and other.user else None,
        },
        me.id,
    )


# ── Recommendations ("Your agent suggests") + manual A2A trigger ────────────
def _require_owned_agent(db: Session, agent_id: str, user: User):
    """Resolve an agent the caller owns, or an (error_response) tuple."""
    a = db.query(Agent).filter(Agent.id == agent_id).first()
    if not a:
        return None, fail("AGENT_NOT_FOUND", "Agent not found", 404)
    if a.user_id != user.id:
        return None, fail("FORBIDDEN", "Not your agent", 403)
    return a, None


@router.get("/agents/{agent_id}/recommendations")
def get_recommendations(
    agent_id: str,
    include_seen: bool = False,
    limit: int = 10,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """The owner-facing 'people you should meet' list produced by the A2A cycle."""
    agent, error = _require_owned_agent(db, agent_id, user)
    if error:
        return error
    items = a2a_recommendations.recommendations_for_agent(
        db, agent.id, include_seen=include_seen, limit=min(max(limit, 1), 50)
    )
    return ok({"items": items}, agent.id)


@router.post("/agents/{agent_id}/recommendations/{rec_id}/seen")
def mark_recommendation_seen(
    agent_id: str,
    rec_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    agent, error = _require_owned_agent(db, agent_id, user)
    if error:
        return error
    marked = a2a_recommendations.mark_recommendation_seen(db, agent.id, rec_id)
    if not marked:
        return fail("RECOMMENDATION_NOT_FOUND", "Recommendation not found", 404)
    return ok({"seen": True, "id": rec_id}, agent.id)


@router.post("/agents/{agent_id}/recommendations/seen-all")
def mark_all_recommendations_seen(
    agent_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    agent, error = _require_owned_agent(db, agent_id, user)
    if error:
        return error
    n = a2a_recommendations.mark_all_seen(db, agent.id)
    return ok({"marked_seen": n}, agent.id)


@router.post("/agents/{agent_id}/run-a2a")
@limiter.limit("6/minute")
def run_a2a(
    agent_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Trigger one full A2A cycle now (for dev / demo) and return what the agent
    decided: who it scanned, who it reached out to, and who it recommends."""
    agent, error = _require_owned_agent(db, agent_id, user)
    if error:
        return error
    sync_agent_profile(db, agent)
    summary = a2a_recommendations.run_a2a_cycle(db, agent)
    cache.invalidate(f"discover_rich:{agent.id}:10")
    return ok(summary, agent.id)


# ── Public profile ─────────────────────────────────────────────────────────
@router.get("/agents/{agent_id}/profile")
def public_profile(agent_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    a = db.query(Agent).filter(Agent.id == agent_id).first()
    if not a:
        return fail("AGENT_NOT_FOUND", "Agent not found", 404)
    compat = None
    if user.agent and user.agent.id != a.id:
        compat = compute_compatibility(user.agent, a)["score"]
    return ok(
        _public_profile(db, a, compat=compat, bio=True),
        user.agent.id if user.agent else None,
    )


# ── Platform stats ─────────────────────────────────────────────────────────
@router.get("/network/stats")
def network_stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    from datetime import timedelta

    day_ago = datetime.utcnow() - timedelta(days=1)
    week_ago = datetime.utcnow() - timedelta(days=7)
    total_agents = db.query(func.count(Agent.id)).scalar() or 0
    conns_today = db.query(func.count(AgentConnection.id)).filter(
        AgentConnection.created_at >= day_ago
    ).scalar() or 0
    inter_week = db.query(func.count(AgentInteraction.id)).filter(
        AgentInteraction.created_at >= week_ago
    ).scalar() or 0

    tag_counts: dict[str, int] = {}
    for (tags,) in db.query(Agent.interest_tags).all():
        for t in tags or []:
            tag_counts[t] = tag_counts.get(t, 0) + 1
    top_tags = sorted(tag_counts.items(), key=lambda x: x[1], reverse=True)[:8]

    return ok({
        "total_agents": total_agents,
        "connections_today": conns_today,
        "interactions_this_week": inter_week,
        "top_interest_tags": [{"tag": t, "count": c} for t, c in top_tags],
    }, user.agent.id if user.agent else None)
