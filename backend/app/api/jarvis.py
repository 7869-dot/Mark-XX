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
from app.services import user_profile as profiles
from app.services import email_agent, feed_agent, web_agent
from app.services.agent_runs import last_runs

router = APIRouter(tags=["jarvis"])


# ── Session orchestration (Section 4 + 6) ─────────────────────────────────────
@router.post("/jarvis/session/start")
@limiter.limit("20/minute")
def jarvis_session_start(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Start a Jarvis session: triggers the three sub-agents, synthesises a
    briefing + 3 action items, and returns it. On first interaction (Jarvis not
    yet onboarded) returns an onboarding payload (greeting + 5 questions) instead
    of running the sub-agents."""
    return envelope(jarvis_orchestrator.run_session(db, user))


# ── Memory profile (Section 6) ────────────────────────────────────────────────
@router.get("/jarvis/memory")
def get_memory(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """The user's Jarvis memory profile."""
    profile = profiles.get_or_create_profile(db, user)
    return envelope({"profile": profiles.profile_dict(profile)})


class MemoryPatch(BaseModel):
    # Onboarding answers (keyed by question id) — when present, runs the
    # onboarding mapping and marks Jarvis onboarding complete.
    answers: dict | None = None
    # Or a direct field patch (interests/hates/goals/communication_style/
    # opportunity_preferences/feedback_log/onboarding_complete).
    interests: list | None = None
    hates: list | None = None
    goals: dict | None = None
    communication_style: str | None = None
    opportunity_preferences: list | None = None


@router.patch("/jarvis/memory")
def patch_memory(
    body: MemoryPatch,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Update the memory profile — from onboarding (body.answers) or a direct
    field patch."""
    if body.answers is not None:
        profile = profiles.apply_onboarding(db, user, body.answers)
    else:
        patch = body.model_dump(exclude_none=True, exclude={"answers"})
        profile = profiles.update_profile(db, user, patch)
    return envelope({"profile": profiles.profile_dict(profile)})


# ── Sub-agent on-demand runs + status + feedback (Section 6) ──────────────────
@router.post("/agents/email/run")
@limiter.limit("20/minute")
def run_email_agent(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return envelope({"report": email_agent.run_report(db, user)})


@router.post("/agents/feed/run")
@limiter.limit("20/minute")
def run_feed_agent(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return envelope({"report": feed_agent.run_report(db, user)})


@router.post("/agents/web/run")
@limiter.limit("20/minute")
def run_web_agent(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    return envelope({"report": web_agent.run_report(db, user)})


@router.get("/agents/status")
def agents_status(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Last run time + one-line summary + status for all three sub-agents."""
    runs = last_runs(db, user.id)
    items = [
        {
            "agent_name": name,
            "last_run": (row.ran_at.isoformat() if row else None),
            "last_summary": (row.report_summary if row else None),
            "status": (row.status if row else "idle"),
        }
        for name, row in runs.items()
    ]
    return envelope({"agents": items})


class WebFeedbackIn(BaseModel):
    result_id: str
    feedback: str  # "useful" | "not_useful"


@router.post("/agents/web/feedback")
def web_feedback(
    body: WebFeedbackIn,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Thumbs up/down on a web-scout result — tunes future scans via feedback_log."""
    ok = profiles.record_feedback(db, user, body.result_id, body.feedback)
    if not ok:
        raise HTTPException(status_code=400, detail="invalid result_id or feedback value")
    return envelope({"recorded": True})


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
