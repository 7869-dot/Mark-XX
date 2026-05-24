"""Marketplace endpoints: browse templates, preview a clone, and execute it.

Templates are world-readable (no auth needed to GET the catalogue). The
clone flow is two-step: GET /clone/preview shows the diff, then
POST /clone with `{ "confirmed": true }` actually applies it. Calling
POST without confirmation returns 409 with the same preview payload so a
client that lost state can still recover.
"""
from typing import Optional

from fastapi import APIRouter, Body, Depends, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.envelope import envelope
from app.core.db import get_db
from app.core.security import get_current_user
from app.models import AgentTemplate, User
from app.services.agent_service import get_primary_agent
from app.services.marketplace import (
    clone_to_user_agent,
    list_templates,
    preview_clone,
    template_dict,
)

router = APIRouter(tags=["marketplace"])


class CloneRequest(BaseModel):
    confirmed: bool | None = None


def _require_template(db: Session, template_id: str) -> AgentTemplate:
    t = db.query(AgentTemplate).filter(AgentTemplate.id == template_id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Template not found")
    return t


@router.get("/marketplace")
def get_marketplace(db: Session = Depends(get_db)):
    """All templates, ordered by clone_count desc then created_at asc."""
    return envelope({"items": list_templates(db)})


@router.get("/marketplace/{template_id}")
def get_marketplace_template(template_id: str, db: Session = Depends(get_db)):
    return envelope(template_dict(_require_template(db, template_id)))


@router.get("/marketplace/{template_id}/clone/preview")
def preview_marketplace_clone(
    template_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Two-column diff: current agent vs what cloning will set. Drives the
    confirmation modal — same payload the 409 from POST /clone returns."""
    t = _require_template(db, template_id)
    agent = get_primary_agent(db, user.id)
    return envelope(preview_clone(agent, t), agent_id=agent.id if agent else None)


@router.post("/marketplace/{template_id}/clone")
def clone_marketplace_template(
    template_id: str,
    payload: CloneRequest = Body(default_factory=CloneRequest),
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Apply this template to the calling user's primary agent.

    Requires an explicit `{ "confirmed": true }` body. Without it, returns
    409 with the same preview payload — so a client that just lost state
    has the same data it would have shown in its modal.
    """
    t = _require_template(db, template_id)

    if not payload.confirmed:
        agent = get_primary_agent(db, user.id)
        body = {
            "success": False,
            "data": None,
            "error": "confirm_required",
            "message": "Confirm required — send { confirmed: true } to proceed",
            "code": "confirm_required",
            "preview": preview_clone(agent, t),
            "meta": {
                "agent_id": agent.id if agent else None,
            },
        }
        return JSONResponse(status_code=409, content=body)

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
