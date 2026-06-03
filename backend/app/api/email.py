"""Email Agent API — the canonical /email surface Jarvis delegates inbox work to.

Thin HTTP adapters over services.email_agent (the single source of truth for
inbox triage + draft generation). No business logic lives here.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.envelope import envelope
from app.core.db import get_db
from app.core.ratelimit import limiter
from app.core.security import get_current_user
from app.models import User
from app.schemas.jarvis import AgentTask
from app.services import email_agent

router = APIRouter(prefix="/email", tags=["email-agent"])


@router.get("/summary")
@limiter.limit("30/minute")
def email_summary(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Structured inbox triage: urgent / important / low buckets + counts.
    Returns {connected, urgent[], important[], low[], action_required[], counts}.
    Empty buckets (not an error) when Gmail isn't connected."""
    return envelope(email_agent.run_report(db, user))


@router.get("/urgent")
@limiter.limit("30/minute")
def email_urgent(request: Request, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    """Just the emails that need the user today — the urgent + action-required
    slice of the triage, with a count. Drives the 'needs you' card."""
    report = email_agent.run_report(db, user)
    return envelope({
        "connected": report.get("connected", False),
        "urgent": report.get("urgent", []),
        "action_required": report.get("action_required", []),
        "urgent_count": report.get("counts", {}).get("urgent", 0),
    })


class DraftRequest(BaseModel):
    instruction: str = Field(..., min_length=1, max_length=2000)


@router.post("/draft")
@limiter.limit("20/minute")
def email_draft(
    request: Request,
    body: DraftRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Draft a reply in the user's voice from a free-form instruction. Stored as
    an approval-gated draft (the agent NEVER sends). Returns the draft row."""
    result = email_agent.execute_task(
        db, AgentTask(agent_role="email", task_description=body.instruction.strip(), priority="today"), user.id
    )
    if not result:
        raise HTTPException(status_code=422, detail="Couldn't draft that — add more on who it's for.")
    return envelope({
        "draft_id": result.id,
        "subject_line": result.subject_line,
        "recipient_hint": result.recipient_hint,
        "draft_content": result.draft_content,
        "requires_approval": result.requires_approval,
    })
