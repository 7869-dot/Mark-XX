"""Marketplace endpoints: browse templates and clone one onto your agent.

Templates are world-readable (no auth needed to GET) — they are public
catalogue rows. POST /marketplace/{id}/clone requires auth and re-themes the
caller's own agent.
"""
from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.api.envelope import envelope
from app.core.db import get_db
from app.core.ratelimit import limiter
from app.core.security import get_current_user
from app.models import AgentTemplate, User
from app.services.marketplace import (
    clone_to_user_agent,
    list_templates,
    template_dict,
)

router = APIRouter(tags=["marketplace"])


@router.get("/marketplace")
def get_marketplace(db: Session = Depends(get_db)):
    """All templates, ordered by clone_count desc then created_at asc."""
    return envelope({"items": list_templates(db)})


@router.get("/marketplace/{template_id}")
def get_marketplace_template(template_id: str, db: Session = Depends(get_db)):
    t = db.query(AgentTemplate).filter(AgentTemplate.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    return envelope(template_dict(t))


@router.post("/marketplace/{template_id}/clone")
def clone_marketplace_template(
    template_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Apply this template to the calling user's agent and increment clone_count.

    The agent is re-themed in place — schema is one-agent-per-user — so the
    user's social graph (followers, posts, history) is preserved.
    """
    t = db.query(AgentTemplate).filter(AgentTemplate.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    agent = clone_to_user_agent(db, user, t)
    return envelope(
        {
            "agent": {
                "id": agent.id,
                "name": agent.name,
                "bio": agent.bio,
                "avatar_seed": agent.avatar_seed,
                "auto_post_schedule": agent.auto_post_schedule,
            },
            "template": template_dict(t),
        },
        agent_id=agent.id,
    )
