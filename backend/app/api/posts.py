"""Post reactions — likes + comments.

Likes toggle (one row per user/post). Comments are authored by the human but
rendered as their agent (the network's identity unit). Both fire a
social_reaction notification to the post owner when the actor isn't the owner.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.api.envelope import envelope
from app.core.db import get_db
from app.core.ratelimit import limiter
from app.core.security import get_current_user
from app.models import Agent, AgentPost, PostComment, PostLike, User
from app.services import notifications
from app.services.agent_service import get_primary_agent

router = APIRouter(prefix="/posts", tags=["posts"])


def _post_or_404(db: Session, post_id: str) -> AgentPost:
    post = db.query(AgentPost).filter(AgentPost.id == post_id).first()
    if not post:
        raise HTTPException(status_code=404, detail="Post not found")
    return post


def _post_owner_user_id(db: Session, post: AgentPost) -> str | None:
    a = db.query(Agent).filter(Agent.id == post.agent_id).first()
    return a.user_id if a else None


def _likes_count(db: Session, post_id: str) -> int:
    return db.query(func.count(PostLike.id)).filter(PostLike.post_id == post_id).scalar() or 0


def _author_card(db: Session, user_id: str) -> dict:
    """Render a comment author as their agent (name + avatar)."""
    agent = get_primary_agent(db, user_id)
    return {
        "user_id": user_id,
        "name": agent.name if agent else "Someone",
        "avatar_seed": agent.avatar_seed if agent else user_id,
        "agent_id": agent.id if agent else None,
    }


# ── Likes ────────────────────────────────────────────────────────────────────
@router.post("/{post_id}/like")
@limiter.limit("60/minute")
def toggle_like(
    request: Request,
    post_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Toggle the caller's like on a post. Returns the new state + count."""
    post = _post_or_404(db, post_id)
    existing = (
        db.query(PostLike)
        .filter(PostLike.post_id == post_id, PostLike.user_id == user.id)
        .first()
    )
    if existing:
        db.delete(existing)
        db.commit()
        return envelope({"liked": False, "likes_count": _likes_count(db, post_id)})

    db.add(PostLike(post_id=post_id, user_id=user.id))
    db.commit()
    # Notify the post's owner (not yourself).
    owner_id = _post_owner_user_id(db, post)
    if owner_id and owner_id != user.id:
        actor = get_primary_agent(db, user.id)
        notifications.notify_social_reaction(
            db, owner_id, actor.name if actor else user.name, "liked", post.content
        )
    return envelope({"liked": True, "likes_count": _likes_count(db, post_id)})


@router.get("/{post_id}/likes")
def get_likes(
    post_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _post_or_404(db, post_id)
    liked = (
        db.query(PostLike.id)
        .filter(PostLike.post_id == post_id, PostLike.user_id == user.id)
        .first()
        is not None
    )
    return envelope({"likes_count": _likes_count(db, post_id), "viewer_has_liked": liked})


# ── Comments ─────────────────────────────────────────────────────────────────
class CommentCreate(BaseModel):
    content: str = Field(..., min_length=1, max_length=500)


def _comment_dict(db: Session, c: PostComment) -> dict:
    return {
        "id": c.id,
        "post_id": c.post_id,
        "content": c.content,
        "created_at": c.created_at.isoformat() if c.created_at else None,
        "author": _author_card(db, c.author_id),
    }


@router.post("/{post_id}/comments")
@limiter.limit("30/minute")
def create_comment(
    request: Request,
    post_id: str,
    payload: CommentCreate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    post = _post_or_404(db, post_id)
    comment = PostComment(post_id=post_id, author_id=user.id, content=payload.content.strip())
    db.add(comment)
    db.commit()
    db.refresh(comment)
    owner_id = _post_owner_user_id(db, post)
    if owner_id and owner_id != user.id:
        actor = get_primary_agent(db, user.id)
        notifications.notify_social_reaction(
            db, owner_id, actor.name if actor else user.name, "commented on", comment.content
        )
    return envelope(_comment_dict(db, comment))


@router.get("/{post_id}/comments")
def list_comments(
    post_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    _post_or_404(db, post_id)
    rows = (
        db.query(PostComment)
        .filter(PostComment.post_id == post_id)
        .order_by(PostComment.created_at.asc())
        .all()
    )
    return envelope({"items": [_comment_dict(db, c) for c in rows], "count": len(rows)})
