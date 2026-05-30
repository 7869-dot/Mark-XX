import uuid
from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.core.db import get_db
from app.core.security import get_current_user
from app.models import User, Agent, Task, AgentInteraction, AgentActivityLog, AgentMessage
from app.api.envelope import envelope
from app.services.activity_feed import build_feed
from app.services.agent_service import create_agent_for_user


router = APIRouter(prefix="/agent", tags=["agent"])


def _agent_dict(agent: Agent) -> dict:
    return {
        "id": agent.id,
        "user_id": agent.user_id,
        "name": agent.name,
        "bio": agent.bio,
        "personality_vector": agent.personality_vector or {},
        "reputation_score": agent.reputation_score,
        "social_graph": agent.social_graph or [],
        "status": agent.status.value if hasattr(agent.status, "value") else agent.status,
        "current_task": agent.current_task,
        "total_tasks_completed": agent.total_tasks_completed,
        "avatar_seed": agent.avatar_seed,
        "avatar_url": agent.avatar_url,
        "interest_tags": agent.interest_tags or [],
        # Social persona (Sprint 3).
        "voice_tone": agent.voice_tone,
        "posting_style": agent.posting_style,
        "response_style": agent.response_style,
        "core_interests": agent.core_interests or [],
        "posting_frequency_bias": (
            agent.posting_frequency_bias if agent.posting_frequency_bias is not None else 1.0
        ),
        "created_at": agent.created_at.isoformat(),
        "last_active_at": agent.last_active_at.isoformat() if agent.last_active_at else None,
        "user_name": agent.user.name if agent.user else None,
        "user_email": agent.user.email if agent.user else None,
        "onboarding_complete": bool(agent.user.onboarding_complete) if agent.user else False,
        "goals": (agent.user.goals if agent.user else []) or [],
    }


@router.get("/me")
def get_me(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    # Compensating creation: a user must never be agent-less. Self-heals any
    # row that slipped through (e.g. a half-failed registration).
    if not user.agent:
        create_agent_for_user(db, user)
        db.refresh(user)
    return envelope(_agent_dict(user.agent), agent_id=user.agent.id)


@router.put("/me")
def update_me(payload: dict, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    agent = user.agent
    if not agent:
        raise HTTPException(status_code=404, detail="No agent")
    if "name" in payload and payload["name"]:
        agent.name = payload["name"]
    if "bio" in payload:
        bio = (payload["bio"] or "").strip()
        agent.bio = bio[:280] or None
    if "avatar_seed" in payload and payload["avatar_seed"]:
        agent.avatar_seed = str(payload["avatar_seed"])[:64]
    if "goals" in payload:
        user.goals = payload["goals"] or []
    if "personality_vector" in payload:
        agent.personality_vector = payload["personality_vector"]
    if "onboarded" in payload:
        user.onboarded = payload["onboarded"]
    # ── Social persona (Sprint 3) ──
    for field in ("voice_tone", "posting_style", "response_style"):
        if field in payload:
            val = (payload[field] or "").strip() if payload[field] else None
            setattr(agent, field, (val[:48] if val else None))
    if "core_interests" in payload and isinstance(payload["core_interests"], list):
        agent.core_interests = [str(t).strip()[:40] for t in payload["core_interests"] if str(t).strip()][:10]
    if "interest_tags" in payload and isinstance(payload["interest_tags"], list):
        agent.interest_tags = [str(t).strip()[:40] for t in payload["interest_tags"] if str(t).strip()][:16]
    if "posting_frequency_bias" in payload:
        try:
            agent.posting_frequency_bias = max(0.1, min(3.0, float(payload["posting_frequency_bias"])))
        except (TypeError, ValueError):
            pass
    if "avatar_url" in payload:
        agent.avatar_url = (str(payload["avatar_url"])[:512] or None) if payload["avatar_url"] else None
    db.commit()
    db.refresh(agent)
    return envelope(_agent_dict(agent), agent_id=agent.id)


@router.get("/activity-feed")
def activity_feed(
    limit: int = 30,
    offset: int = 0,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not user.agent:
        raise HTTPException(status_code=404, detail="No agent")
    items = build_feed(db, user.agent, limit=limit, offset=offset)
    return envelope({"items": items, "next_offset": offset + len(items)}, agent_id=user.agent.id)


# Canonical human-time-saved estimates per task type (minutes).
TIME_SAVED_PER_TYPE = {
    "research": 45,
    "outreach": 30,
    "scheduling": 20,
    "analysis": 60,
    "networking": 40,
    "negotiation": 90,
    "monitoring": 15,
}


@router.get("/stats")
def stats(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    agent = user.agent
    if not agent:
        raise HTTPException(status_code=404, detail="No agent")

    # "Today" = midnight UTC → now, not last-24h, so users see counters reset
    # on the day boundary like every other dashboard product. Week = last 7d.
    now = datetime.utcnow()
    today_start = now.replace(hour=0, minute=0, second=0, microsecond=0)
    week_start = now - timedelta(days=7)

    # Activity-driven counters — every "the agent did X" passes through the
    # log via activity_logger, so these are the canonical "proof of life".
    activity_today = db.query(func.count(AgentActivityLog.id)).filter(
        AgentActivityLog.agent_id == agent.id,
        AgentActivityLog.created_at >= today_start,
    ).scalar() or 0
    activity_week = db.query(func.count(AgentActivityLog.id)).filter(
        AgentActivityLog.agent_id == agent.id,
        AgentActivityLog.created_at >= week_start,
    ).scalar() or 0
    activity_total = db.query(func.count(AgentActivityLog.id)).filter(
        AgentActivityLog.agent_id == agent.id
    ).scalar() or 0

    # Task counters retained for the queue UI and time-saved math.
    tasks_today = db.query(func.count(Task.id)).filter(
        Task.agent_id == agent.id, Task.created_at >= today_start
    ).scalar() or 0
    tasks_week = db.query(func.count(Task.id)).filter(
        Task.agent_id == agent.id, Task.created_at >= week_start
    ).scalar() or 0
    tasks_total = db.query(func.count(Task.id)).filter(Task.agent_id == agent.id).scalar() or 0

    interactions_today = db.query(func.count(AgentInteraction.id)).filter(
        ((AgentInteraction.initiator_agent_id == agent.id) |
         (AgentInteraction.target_agent_id == agent.id)),
        AgentInteraction.created_at >= today_start,
    ).scalar() or 0

    # Connections = distinct other agents this agent has actually exchanged
    # A2A messages with. social_graph is legacy and almost always empty.
    sender_ids = db.query(AgentMessage.sender_agent_id).filter(
        AgentMessage.recipient_agent_id == agent.id
    ).distinct().all()
    recipient_ids = db.query(AgentMessage.recipient_agent_id).filter(
        AgentMessage.sender_agent_id == agent.id
    ).distinct().all()
    connected_ids = {r[0] for r in sender_ids} | {r[0] for r in recipient_ids}
    connected_ids.discard(agent.id)
    connection_avatars = []
    if connected_ids:
        rows = db.query(Agent.id, Agent.name, Agent.avatar_seed).filter(
            Agent.id.in_(connected_ids)
        ).limit(8).all()
        connection_avatars = [
            {"id": r[0], "name": r[1], "avatar_seed": r[2]} for r in rows
        ]

    def _saved(tasks) -> int:
        return sum(
            TIME_SAVED_PER_TYPE.get(
                t.task_type.value if hasattr(t.task_type, "value") else t.task_type, 20
            )
            for t in tasks
        )

    completed = db.query(Task).filter(
        Task.agent_id == agent.id, Task.status == "completed"
    ).all()
    completed_week = [
        t for t in completed if (t.completed_at or t.created_at) >= week_start
    ]

    return envelope({
        # Canonical "agent did stuff today" counters — drive the SIGNAL column.
        "actions_today": activity_today,
        "actions_week": activity_week,
        "actions_total": activity_total,
        # Aliased to the legacy keys the frontend already reads so unchanged
        # consumers light up immediately. New UI should prefer `actions_*`.
        "tasks_today": activity_today,
        "tasks_week": activity_week,
        "tasks_total": activity_total,
        # Raw task counters retained for queue/time-saved consumers.
        "raw_tasks_today": tasks_today,
        "raw_tasks_week": tasks_week,
        "raw_tasks_total": tasks_total,
        "connections": len(connected_ids),
        "connection_avatars": connection_avatars,
        "interactions_today": interactions_today,
        "time_saved_minutes": _saved(completed),
        "time_saved_minutes_week": _saved(completed_week),
        "reputation_score": agent.reputation_score,
    }, agent_id=agent.id)


@router.post("/regenerate-avatar")
def regenerate_avatar(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    agent = user.agent
    if not agent:
        raise HTTPException(status_code=404, detail="No agent")
    agent.avatar_seed = str(uuid.uuid4())
    db.commit()
    return envelope({"avatar_seed": agent.avatar_seed}, agent_id=agent.id)
