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
from app.models import AgentTaskResult, ScheduleDraft, PostDraft, User
from app.schemas.jarvis import JarvisChatRequest
from app.services import jarvis_orchestrator, jarvis_router

router = APIRouter(tags=["jarvis"])


# ── Chat command modes (Sprint 3A) ───────────────────────────────────────────
@router.post("/jarvis/chat")
@limiter.limit("40/minute")
def jarvis_chat(
    request: Request,
    body: JarvisChatRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Talk to Jarvis in one of five modes. Jarvis always replies in-character;
    EMAIL/SCHEDULE/POST also return an approval-gated draft action, RESEARCH
    returns an inline synthesis. The exchange is persisted to chat history."""
    resp = jarvis_router.route_chat(db, user, body.message.strip(), body.mode, body.context)
    return envelope(resp.model_dump(mode="json"))


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


# ── Schedule drafts (Sprint 3A) ──────────────────────────────────────────────
def _schedule_dict(s: ScheduleDraft) -> dict:
    return {
        "id": s.id,
        "title": s.title,
        "proposed_datetime": s.proposed_datetime.isoformat() if s.proposed_datetime else None,
        "duration_minutes": s.duration_minutes,
        "attendees_hint": s.attendees_hint or [],
        "notes": s.notes,
        "approved": s.approved,
        "created_at": s.created_at.isoformat() if s.created_at else None,
    }


@router.get("/agents/schedule-drafts")
def list_schedule_drafts(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (
        db.query(ScheduleDraft)
        .filter(ScheduleDraft.user_id == user.id, ScheduleDraft.approved.is_(None))
        .order_by(ScheduleDraft.created_at.desc())
        .all()
    )
    return envelope({"items": [_schedule_dict(s) for s in rows]})


@router.patch("/agents/schedule-drafts/{draft_id}")
def decide_schedule_draft(
    draft_id: str,
    body: DraftDecision,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Approve or reject a schedule draft. V1: NO calendar write — approving just
    records the decision (real OAuth calendar write is Sprint 4)."""
    s = (
        db.query(ScheduleDraft)
        .filter(ScheduleDraft.id == draft_id, ScheduleDraft.user_id == user.id)
        .first()
    )
    if not s:
        raise HTTPException(status_code=404, detail="schedule draft not found")
    s.approved = bool(body.approved)
    db.commit()
    return envelope({"id": s.id, "approved": s.approved, "booked": False})


# ── Post drafts (Sprint 3A) ──────────────────────────────────────────────────
# NOTE: post_drafts is NOT the social feed. The feed_autopost / world_post
# sweeps never read this table — a post reaches the social layer only after the
# posting agent's approval flow (real publish wired in a later sprint).
@router.get("/agents/post-drafts")
def list_post_drafts(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    rows = (
        db.query(PostDraft)
        .filter(PostDraft.user_id == user.id, PostDraft.approved.is_(None))
        .order_by(PostDraft.created_at.desc())
        .all()
    )
    return envelope({"items": [
        {
            "id": p.id, "content": p.content, "island_hint": p.island_hint,
            "approved": p.approved,
            "created_at": p.created_at.isoformat() if p.created_at else None,
        }
        for p in rows
    ]})


@router.patch("/agents/post-drafts/{draft_id}")
def decide_post_draft(
    draft_id: str,
    body: DraftDecision,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Approve or kill a post draft. V1: approving records the decision but does
    NOT publish to the social layer — that stays behind the posting agent."""
    p = (
        db.query(PostDraft)
        .filter(PostDraft.id == draft_id, PostDraft.user_id == user.id)
        .first()
    )
    if not p:
        raise HTTPException(status_code=404, detail="post draft not found")
    if body.approved and body.content is not None:
        p.content = body.content.strip()
    p.approved = bool(body.approved)
    db.commit()
    return envelope({"id": p.id, "approved": p.approved, "posted": False})
