"""Email Intelligence — surfaces classified emails to the dashboard.

Read-side: separate URGENT_HUMAN and AGENT_HANDLEABLE rows so the UI can render
them in their two distinct sections. Write-side: approve/edit/discard the
agent's pre-drafted reply.
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models import (
    ActivityType,
    Agent,
    ClassifiedEmail,
    EmailCategory,
    User,
)
from app.api.envelope import envelope
from app.services import gmail_service
from app.services.activity_logger import log_activity
from app.services.email_classifier import classify_recent_for_user

router = APIRouter(prefix="/emails", tags=["email-intel"])


def _serialize(r: ClassifiedEmail) -> dict:
    return {
        "id": r.id,
        "email_id": r.email_id,
        "thread_id": r.thread_id,
        "sender": r.sender,
        "sender_email": r.sender_email,
        "subject": r.subject,
        "snippet": r.snippet,
        "category": r.category.value,
        "reason": r.reason,
        "suggested_action": r.suggested_action,
        "drafted_reply": r.drafted_reply,
        "draft_status": r.draft_status,
        "dismissed": r.dismissed,
        "created_at": r.created_at.isoformat(),
    }


@router.get("/classified")
def list_classified(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    rows = (
        db.query(ClassifiedEmail)
        .filter(
            ClassifiedEmail.user_id == user.id,
            ClassifiedEmail.dismissed == False,  # noqa: E712
        )
        .order_by(ClassifiedEmail.created_at.desc())
        .limit(80)
        .all()
    )
    urgent = [_serialize(r) for r in rows if r.category == EmailCategory.urgent_human]
    drafts = [
        _serialize(r) for r in rows
        if r.category == EmailCategory.agent_handleable
        and r.draft_status in {"pending", "edited"}
    ]
    informational = [
        _serialize(r) for r in rows
        if r.category in {EmailCategory.informational, EmailCategory.spam}
    ][:10]
    return envelope({
        "urgent_count": len(urgent),
        "drafts_count": len(drafts),
        "urgent": urgent,
        "drafts": drafts,
        "informational": informational,
    })


@router.post("/refresh")
def refresh_classifications(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Manual trigger — the scheduler also runs this every 30 min."""
    if not getattr(user, "gmail_connected", False):
        raise HTTPException(status_code=400, detail="Gmail is not connected")
    n = classify_recent_for_user(db, user)
    return envelope({"classified": n})


class DraftUpdate(BaseModel):
    body: str = Field(..., min_length=1, max_length=8000)


@router.post("/{email_id}/draft/edit")
def edit_draft(
    email_id: str,
    body: DraftUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = (
        db.query(ClassifiedEmail)
        .filter(ClassifiedEmail.user_id == user.id, ClassifiedEmail.id == email_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="not_found")
    row.drafted_reply = body.body.strip()
    row.draft_status = "edited"
    db.commit()
    db.refresh(row)
    return envelope(_serialize(row))


@router.post("/{email_id}/draft/approve")
def approve_draft(
    email_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = (
        db.query(ClassifiedEmail)
        .filter(ClassifiedEmail.user_id == user.id, ClassifiedEmail.id == email_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="not_found")
    if not row.drafted_reply:
        raise HTTPException(status_code=400, detail="no_draft")
    # Send via gmail_service (stub-aware — no-op in dev).
    try:
        gmail_service.send_email(
            db, user.id,
            to=row.sender_email or row.sender,
            subject=("Re: " + row.subject) if not row.subject.lower().startswith("re:") else row.subject,
            body=row.drafted_reply,
            reply_to_thread_id=row.thread_id,
        )
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"send_failed: {exc}")

    row.draft_status = "sent"
    db.commit()
    db.refresh(row)
    agent: Agent | None = next((a for a in user.agents if a.is_primary), None)
    if agent:
        log_activity(
            db, agent.id, ActivityType.email_sent,
            f"Sent reply to {row.sender or row.sender_email}.",
            metadata={"email_id": row.email_id},
        )
    return envelope(_serialize(row))


@router.post("/{email_id}/draft/discard")
def discard_draft(
    email_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = (
        db.query(ClassifiedEmail)
        .filter(ClassifiedEmail.user_id == user.id, ClassifiedEmail.id == email_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="not_found")
    row.draft_status = "discarded"
    db.commit()
    db.refresh(row)
    return envelope(_serialize(row))


@router.post("/{email_id}/dismiss")
def dismiss(
    email_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    row = (
        db.query(ClassifiedEmail)
        .filter(ClassifiedEmail.user_id == user.id, ClassifiedEmail.id == email_id)
        .first()
    )
    if not row:
        raise HTTPException(status_code=404, detail="not_found")
    row.dismissed = True
    db.commit()
    return envelope({"dismissed": True})
