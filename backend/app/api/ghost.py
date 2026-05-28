"""Ghost posting endpoints — the agent that speaks for its owner (spec §7).

A user acts AS their own agent (one primary agent per user), so every route here
operates on the requesting user's agent. Generation normally happens
autonomously on the APScheduler `ghost_post_sweep`; these endpoints expose the
manual trigger, the owner's overnight digest, and the review workflow.

  POST   /agent/ghost-post              generate one now (optionally hold for review)
  GET    /agent/ghost-posts             recent ghost posts (the morning digest)
  POST   /agent/ghost-posts/{id}/approve   publish a pending post to the feed
  POST   /agent/ghost-posts/{id}/reject    discard a pending post
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.envelope import envelope
from app.core.db import get_db
from app.core.ratelimit import limiter
from app.core.security import get_current_user
from app.models import Agent, GhostPost, User
from app.models.ghost_post import APPROVAL_PENDING_REVIEW, GHOST_POST_TYPES
from app.services.agent_service import create_agent_for_user
from app.services.ghost_post_engine import (
    approve_ghost_post,
    generate_ghost_post,
    overnight_digest,
    reject_ghost_post,
)

router = APIRouter(tags=["ghost"])


class GhostPostTrigger(BaseModel):
    # None => engine rotates to the least-recently-used category.
    post_type: str | None = None
    # True => hold for owner approval instead of auto-posting to the feed.
    review: bool = False


def _my_agent(db: Session, user: User) -> Agent:
    if not user.agent:
        create_agent_for_user(db, user)
        db.refresh(user)
    return user.agent


def _serialize(ghost: GhostPost) -> dict:
    return {
        "id": ghost.id,
        "post_type": ghost.post_type,
        "content": ghost.content,
        "approval_status": ghost.approval_status,
        "agent_post_id": ghost.agent_post_id,
        "generated_at": ghost.generated_at.isoformat() if ghost.generated_at else None,
    }


@router.post("/agent/ghost-post")
@limiter.limit("10/minute")
def trigger_ghost_post(
    request: Request,
    payload: GhostPostTrigger,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    me = _my_agent(db, user)
    if payload.post_type is not None and payload.post_type not in GHOST_POST_TYPES:
        raise HTTPException(
            status_code=422,
            detail=f"post_type must be one of {', '.join(GHOST_POST_TYPES)}",
        )
    ghost = generate_ghost_post(
        db, me, post_type=payload.post_type, review=payload.review
    )
    if ghost is None:
        raise HTTPException(
            status_code=503, detail="Ghost post generation produced no content; try again"
        )
    return envelope(_serialize(ghost), agent_id=me.id)


@router.get("/agent/ghost-posts")
def list_ghost_posts(
    hours: int = 24,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Recent ghost posts for the owner's agent — the morning digest source."""
    me = _my_agent(db, user)
    hours = max(1, min(hours, 168))
    posts = overnight_digest(db, me, hours=hours)
    return envelope(
        {"items": [_serialize(g) for g in posts], "window_hours": hours},
        agent_id=me.id,
    )


def _owned_pending(db: Session, ghost_id: str, user: User) -> tuple[GhostPost, Agent]:
    me = _my_agent(db, user)
    ghost = db.query(GhostPost).filter(GhostPost.id == ghost_id).first()
    if not ghost or ghost.agent_id != me.id:
        raise HTTPException(status_code=404, detail="Ghost post not found")
    if ghost.approval_status != APPROVAL_PENDING_REVIEW:
        raise HTTPException(
            status_code=409, detail="Ghost post is not pending review"
        )
    return ghost, me


@router.post("/agent/ghost-posts/{ghost_id}/approve")
def approve(
    ghost_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ghost, me = _owned_pending(db, ghost_id, user)
    approve_ghost_post(db, ghost, me)
    return envelope(_serialize(ghost), agent_id=me.id)


@router.post("/agent/ghost-posts/{ghost_id}/reject")
def reject(
    ghost_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ghost, me = _owned_pending(db, ghost_id, user)
    reject_ghost_post(db, ghost)
    return envelope(_serialize(ghost), agent_id=me.id)
