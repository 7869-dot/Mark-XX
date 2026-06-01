"""Jarvis wake-up + agent draft queue API (Sprint 2)."""
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.envelope import envelope
from app.core.db import get_db
from app.core.ratelimit import limiter
from app.core.security import get_current_user
from app.models import AgentTaskResult, User
from app.services import jarvis_orchestrator

router = APIRouter(tags=["jarvis"])


@router.get("/jarvis/context")
@limiter.limit("60/minute")
def jarvis_context(
    request: Request,
    refresh: bool = False,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Jarvis wake-up. Returns the cached context within TTL, or regenerates on
    first session login / ?refresh=true. Never blocks login — a Jarvis failure
    returns 200 with context:null so the home screen loads gracefully."""
    ctx = jarvis_orchestrator.wake_up(db, user.id, force=refresh)
    if ctx is None:
        # Graceful: home screen renders without Jarvis rather than 500-ing.
        return envelope({"context": None})
    return envelope({"context": ctx.model_dump(mode="json")})


# ── Draft queue ──────────────────────────────────────────────────────────────
def _draft_dict(r: AgentTaskResult) -> dict:
    return {
        "id": r.id,
        "task_id": r.task_id,
        "agent_role": r.agent_role,
        "subject_line": r.subject_line,
        "recipient_hint": r.recipient_hint,
        "draft_content": r.draft_content,
        "requires_approval": r.requires_approval,
        "approved": r.approved,
        "created_at": r.created_at.isoformat() if r.created_at else None,
    }


@router.get("/agents/drafts")
def list_drafts(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Pending drafts (approved IS NULL) for the user, newest first."""
    rows = (
        db.query(AgentTaskResult)
        .filter(AgentTaskResult.user_id == user.id, AgentTaskResult.approved.is_(None))
        .order_by(AgentTaskResult.created_at.desc())
        .all()
    )
    return envelope({"items": [_draft_dict(r) for r in rows]})


class DraftDecision(BaseModel):
    approved: bool
    content: str | None = None  # optional edited body on approve


@router.patch("/agents/drafts/{draft_id}")
def decide_draft(
    draft_id: str,
    body: DraftDecision,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Approve or kill a draft. V1: approving marks it approved but DOES NOT
    SEND — real send is Sprint 3. Killing sets approved=False."""
    r = (
        db.query(AgentTaskResult)
        .filter(AgentTaskResult.id == draft_id, AgentTaskResult.user_id == user.id)
        .first()
    )
    if not r:
        raise HTTPException(status_code=404, detail="draft not found")
    if body.approved and body.content is not None:
        r.draft_content = body.content.strip()
    r.approved = bool(body.approved)
    # sent_at intentionally stays NULL — no send path in V1.
    db.commit()
    db.refresh(r)
    return envelope({"id": r.id, "approved": r.approved, "sent": False})
