"""Multi-agent management — list, create, promote-to-primary, delete.

The schema already supports multiple agents per user (Sprint 3 hardening:
agents.is_primary + partial unique index). These endpoints expose that
to the product layer.

Distinct from /agent/* (singular) which owns the primary-agent profile.

NOTE: do NOT add `from __future__ import annotations` here — it stringifies
the AgentCreate annotation on `payload`, which prevents FastAPI/pydantic
from resolving the request body schema and silently returns body_params=[].
"""
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.envelope import envelope
from app.core.db import get_db
from app.core.ratelimit import limiter
from app.core.security import get_current_user
from app.models import (
    Agent,
    AgentAlert,
    AgentFollow,
    AgentMemory,
    AgentPost,
    ScheduledJob,
    User,
    WatchedThread,
)
from app.models.agent import AgentStatus, DEFAULT_PERSONALITY
from app.services.scheduler_service import ensure_default_jobs

router = APIRouter(tags=["agents"])


class AgentCreate(BaseModel):
    name: str = Field(..., min_length=1, max_length=60)
    bio: Optional[str] = Field(default=None, max_length=280)
    avatar_seed: Optional[str] = Field(default=None, max_length=64)
    personality_vector: Optional[dict] = None


class AgentEdit(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=60)
    bio: Optional[str] = Field(default=None, max_length=280)
    avatar_seed: Optional[str] = Field(default=None, max_length=64)
    personality_vector: Optional[dict] = None


def _owned_agent(db: Session, agent_id: str, user: User) -> Agent:
    ag = db.query(Agent).filter(Agent.id == agent_id).first()
    if not ag:
        raise HTTPException(status_code=404, detail="Agent not found")
    if ag.user_id != user.id:
        raise HTTPException(status_code=403, detail="Not your agent")
    return ag


def _agent_summary(db: Session, agent: Agent) -> dict:
    follower_count = (
        db.query(func.count(AgentFollow.id))
        .filter(AgentFollow.following_agent_id == agent.id)
        .scalar()
        or 0
    )
    return {
        "id": agent.id,
        "name": agent.name,
        "bio": agent.bio,
        "avatar_seed": agent.avatar_seed,
        "is_primary": bool(agent.is_primary),
        "role": agent.role,
        "follower_count": follower_count,
        "auto_post_schedule": agent.auto_post_schedule,
        "created_at": agent.created_at.isoformat() if agent.created_at else None,
    }


# ── Team (four-agent architecture) ───────────────────────────────────────────
@router.get("/agents/team")
def my_team(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """The user's four-agent team, keyed by role (posting/jarvis/email/wildcard).
    Self-heals: seeds any missing team members on first read."""
    from app.services.agent_team import ensure_team
    from app.models.agent import AgentRole

    team = ensure_team(db, user)
    order = [AgentRole.jarvis, AgentRole.posting, AgentRole.email, AgentRole.wildcard]
    items = []
    for role in order:
        a = team.get(role.value)
        if not a:
            continue
        d = _agent_summary(db, a)
        d["voice_tone"] = a.voice_tone
        d["system_prompt"] = a.system_prompt
        items.append(d)
    return envelope({"items": items})


# ── List ───────────────────────────────────────────────────────────────────
@router.get("/agents/mine")
def list_my_agents(
    db: Session = Depends(get_db), user: User = Depends(get_current_user)
):
    """The user's posting agents (the public-facing identities they manage).

    Scoped to role='posting' so the four-agent *team* members (jarvis/email/
    wildcard) don't appear here — those are surfaced via GET /agents/team. A
    user may still own multiple posting agents (the multi-agent feature)."""
    from app.models.agent import AgentRole

    rows = (
        db.query(Agent)
        .filter(Agent.user_id == user.id, Agent.role == AgentRole.posting.value)
        .order_by(Agent.is_primary.desc(), Agent.created_at.asc())
        .all()
    )
    return envelope({"items": [_agent_summary(db, a) for a in rows]})


# ── Create ─────────────────────────────────────────────────────────────────
@router.post("/agents")
@limiter.limit("20/minute")
def create_agent(
    request: Request,
    payload: AgentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a new agent for this user. is_primary defaults to False if a
    primary already exists (which is the common case — the first agent is
    created at signup by create_agent_for_user)."""
    has_primary = (
        db.query(Agent)
        .filter(Agent.user_id == user.id, Agent.is_primary == True)  # noqa: E712
        .first()
        is not None
    )
    agent = Agent(
        user_id=user.id,
        is_primary=not has_primary,  # first agent ever for this user => primary
        name=payload.name.strip(),
        bio=(payload.bio or "").strip() or None,
        avatar_seed=payload.avatar_seed or None,
        personality_vector=payload.personality_vector or dict(DEFAULT_PERSONALITY),
        interest_tags=[],
        goals=[],
        total_interactions=0,
        status=AgentStatus.idle,
    )
    db.add(agent)
    db.commit()
    db.refresh(agent)
    ensure_default_jobs(db, agent)
    return envelope(_agent_summary(db, agent), agent_id=agent.id)


# ── Edit ───────────────────────────────────────────────────────────────────
@router.put("/agents/{agent_id}")
def edit_agent(
    agent_id: str,
    payload: AgentEdit,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Edit name/bio/avatar/personality on any of the calling user's agents.

    Distinct from PUT /agent/me, which only touches the primary. This endpoint
    is what the multi-agent management page uses for the "Edit" action.
    """
    target = _owned_agent(db, agent_id, user)
    if payload.name is not None:
        target.name = payload.name.strip()
    if payload.bio is not None:
        bio = payload.bio.strip()
        target.bio = bio[:280] or None
    if payload.avatar_seed is not None:
        target.avatar_seed = payload.avatar_seed[:64]
    if payload.personality_vector is not None:
        target.personality_vector = payload.personality_vector
    db.commit()
    db.refresh(target)
    return envelope(_agent_summary(db, target), agent_id=target.id)


# ── Promote ────────────────────────────────────────────────────────────────
@router.put("/agents/{agent_id}/make-primary")
def make_primary(
    agent_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Atomically promote `agent_id` to primary and demote the current primary.

    The partial unique index (uq_primary_agent_per_user) means we MUST demote
    before promoting, otherwise the commit fails. Wrapped in one transaction.
    """
    target = _owned_agent(db, agent_id, user)
    if target.is_primary:
        # Idempotent — calling make-primary on the current primary is a no-op.
        return envelope(_agent_summary(db, target), agent_id=target.id)

    # Demote ALL currently-primary agents for this user (defensive — there
    # should only ever be one thanks to the partial index).
    db.query(Agent).filter(
        Agent.user_id == user.id, Agent.is_primary == True  # noqa: E712
    ).update({Agent.is_primary: False}, synchronize_session=False)
    db.flush()
    target.is_primary = True
    db.commit()
    db.refresh(target)
    return envelope(_agent_summary(db, target), agent_id=target.id)


# ── Delete ─────────────────────────────────────────────────────────────────
def _cascade_delete_agent(db: Session, agent: Agent) -> None:
    """Explicit cleanup of every FK reference into agents.id that the schema
    doesn't already cascade. AgentMemory and Task cascade via SQLAlchemy
    relationship; the rest we handle here."""
    # Try to import notifications model — exists from WS2 onward.
    try:
        from app.models import AgentNotification

        db.query(AgentNotification).filter(
            AgentNotification.agent_id == agent.id
        ).delete()
    except Exception:  # noqa: BLE001
        pass

    db.query(AgentFollow).filter(
        (AgentFollow.follower_agent_id == agent.id)
        | (AgentFollow.following_agent_id == agent.id)
    ).delete(synchronize_session=False)
    # Likes/comments on this agent's posts (FK cascades on PG, but be explicit so
    # SQLite — where FK enforcement is off in tests — doesn't orphan rows).
    from app.models import PostComment, PostLike

    post_ids = [r[0] for r in db.query(AgentPost.id).filter(AgentPost.agent_id == agent.id).all()]
    if post_ids:
        db.query(PostLike).filter(PostLike.post_id.in_(post_ids)).delete(synchronize_session=False)
        db.query(PostComment).filter(PostComment.post_id.in_(post_ids)).delete(synchronize_session=False)
    db.query(AgentPost).filter(AgentPost.agent_id == agent.id).delete(
        synchronize_session=False
    )
    db.query(AgentAlert).filter(AgentAlert.agent_id == agent.id).delete(
        synchronize_session=False
    )
    db.query(ScheduledJob).filter(ScheduledJob.agent_id == agent.id).delete(
        synchronize_session=False
    )
    db.query(WatchedThread).filter(WatchedThread.agent_id == agent.id).delete(
        synchronize_session=False
    )
    db.query(AgentMemory).filter(AgentMemory.agent_id == agent.id).delete(
        synchronize_session=False
    )
    db.delete(agent)
    db.commit()


@router.delete("/agents/{agent_id}")
def delete_agent(
    agent_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Delete a posting agent. The primary can only be deleted when it's the
    only POSTING agent left. Team agents (jarvis/email/wildcard) are managed as
    a set and can't be deleted individually here."""
    from app.models.agent import AgentRole

    target = _owned_agent(db, agent_id, user)
    if target.role != AgentRole.posting.value:
        raise HTTPException(
            status_code=409,
            detail="Team agents (Jarvis, Inbox, Wildcard) can't be deleted "
            "individually — they're part of your agent team.",
        )
    # Count only other POSTING agents — team members don't block deletion.
    posting_siblings = (
        db.query(func.count(Agent.id))
        .filter(
            Agent.user_id == user.id,
            Agent.id != target.id,
            Agent.role == AgentRole.posting.value,
        )
        .scalar()
        or 0
    )
    if target.is_primary and posting_siblings > 0:
        raise HTTPException(
            status_code=409,
            detail="Cannot delete primary agent while other agents exist — "
            "promote another agent first.",
        )
    _cascade_delete_agent(db, target)
    return envelope({"deleted": True, "id": agent_id})
