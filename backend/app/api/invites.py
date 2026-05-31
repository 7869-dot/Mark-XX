"""Invite codes — generate, list, redeem (Sprint 5 growth loop)."""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.envelope import envelope
from app.core.db import get_db
from app.core.ratelimit import limiter
from app.core.security import get_current_user
from app.models import User
from app.services import invites

router = APIRouter(prefix="/invites", tags=["invites"])


@router.post("/generate")
@limiter.limit("20/minute")
def generate(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Create a fresh single-use invite code for the caller."""
    code = invites.generate_code(db, user)
    return envelope({"code": code.code, "used": False}, agent_id=user.agent.id if user.agent else None)


@router.get("/mine")
def mine(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """The caller's codes + usage status, and how many people they've invited."""
    return envelope(
        {
            "items": invites.codes_for_user(db, user.id),
            "invited_count": invites.invited_count(db, user.id),
        },
        agent_id=user.agent.id if user.agent else None,
    )


class RedeemBody(BaseModel):
    code: str = Field(..., min_length=1, max_length=32)


@router.post("/redeem")
@limiter.limit("10/minute")
def redeem(
    request: Request,
    body: RedeemBody,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Redeem an invite code (called during onboarding). Single-use; on success
    the inviter's agent sends a welcome DM and both users are notified."""
    result = invites.redeem(db, body.code, user)
    return envelope(result, agent_id=user.agent.id if user.agent else None)
