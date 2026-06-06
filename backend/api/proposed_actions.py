"""Proposed actions endpoints.

GET  /proposed-actions              — list pending actions for the user
POST /proposed-actions/{id}/approve — execute the action + mark approved
POST /proposed-actions/{id}/reject  — mark rejected (no side effects)

Approve executes the real Gmail send / Calendar create / connection unlock
depending on action type.  The action is fail-closed: any execution error
leaves status as 'pending' and returns 500 so the user can retry.
"""
from __future__ import annotations

import logging
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from api.deps import current_user_id
from auth import get_valid_access_token
from db import get_db
from models import Briefing, ProposedAction
from tools import gmail_tools, calendar_tools

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/proposed-actions", tags=["proposed-actions"])


# ── Pydantic schemas ───────────────────────────────────────────────────────────

class ProposedActionOut(BaseModel):
    id:         str
    type:       str
    payload:    dict
    rationale:  str
    status:     str
    created_at: str


# ── Helpers ────────────────────────────────────────────────────────────────────

def _get_action_or_404(action_id: str, user_id: str, db: Session) -> ProposedAction:
    action = db.query(ProposedAction).filter_by(id=action_id, user_id=user_id).first()
    if not action:
        raise HTTPException(status_code=404, detail="Proposed action not found.")
    return action


def _fmt(action: ProposedAction) -> dict:
    return {
        "id":         action.id,
        "type":       action.type,
        "payload":    action.payload or {},
        "rationale":  action.rationale or "",
        "status":     action.status,
        "created_at": action.created_at.isoformat() if action.created_at else "",
    }


# ── Endpoints ──────────────────────────────────────────────────────────────────

@router.get("")
async def list_proposed_actions(
    uid: str = Depends(current_user_id),
    db:  Session = Depends(get_db),
    status: str = "pending",
):
    """Return proposed actions for the user, filtered by status (default: pending)."""
    actions = (
        db.query(ProposedAction)
        .filter_by(user_id=uid, status=status)
        .order_by(ProposedAction.created_at.desc())
        .all()
    )
    return [_fmt(a) for a in actions]


@router.post("/{action_id}/approve")
async def approve_action(
    action_id: str,
    uid: str = Depends(current_user_id),
    db:  Session = Depends(get_db),
):
    """
    Approve and execute a proposed action.

    email_reply         → sends via Gmail API
    calendar_event      → creates via Calendar API
    connection_approval → marks the Briefing as seen + triggers contact unlock
                          (full mutual-consent exchange is a TODO)
    """
    action = _get_action_or_404(action_id, uid, db)
    if action.status != "pending":
        raise HTTPException(status_code=409, detail=f"Action is already {action.status}.")

    try:
        access_token = await get_valid_access_token(uid, db)
    except ValueError as exc:
        raise HTTPException(status_code=403, detail=str(exc))

    payload = action.payload or {}
    result_message = ""

    # ── email_reply ────────────────────────────────────────────────────────────
    if action.type == "email_reply":
        try:
            result_message = gmail_tools.send_gmail(
                access_token,
                to=payload.get("to", ""),
                subject=payload.get("subject", ""),
                body=payload.get("body", ""),
                in_reply_to_id=payload.get("in_reply_to_id") or None,
            )
        except Exception as exc:
            logger.error("Email send failed for action %s: %s", action_id, exc)
            raise HTTPException(status_code=500, detail=f"Email send failed: {exc}")

    # ── calendar_event ─────────────────────────────────────────────────────────
    elif action.type == "calendar_event":
        try:
            event = calendar_tools.create_calendar_event(
                access_token,
                title=payload.get("title", ""),
                start=payload.get("start", ""),
                end=payload.get("end", ""),
                description=payload.get("description", ""),
                attendees=payload.get("attendees", []),
            )
            result_message = f"Calendar event '{event['summary']}' created."
        except Exception as exc:
            logger.error("Calendar create failed for action %s: %s", action_id, exc)
            raise HTTPException(status_code=500, detail=f"Calendar create failed: {exc}")

    # ── connection_approval ────────────────────────────────────────────────────
    elif action.type == "connection_approval":
        briefing_id = payload.get("briefing_id")
        if briefing_id:
            briefing = db.query(Briefing).filter_by(id=briefing_id, user_id=uid).first()
            if briefing:
                briefing.seen = True
        # TODO: trigger mutual-consent contact exchange once BOTH users have approved
        # their respective connection_approval proposed_actions.  Until then, no
        # contact data is exchanged — only the briefing is marked seen.
        result_message = (
            f"Connection with {payload.get('partner_name', 'partner')} approved. "
            "Contact exchange will be unlocked once both parties approve."
        )

    else:
        raise HTTPException(status_code=400, detail=f"Unknown action type: {action.type}")

    action.status     = "approved"
    action.updated_at = datetime.utcnow()
    db.commit()
    return {"success": True, "message": result_message, "action": _fmt(action)}


@router.post("/{action_id}/reject")
async def reject_action(
    action_id: str,
    uid: str = Depends(current_user_id),
    db:  Session = Depends(get_db),
):
    action = _get_action_or_404(action_id, uid, db)
    if action.status != "pending":
        raise HTTPException(status_code=409, detail=f"Action is already {action.status}.")
    action.status     = "rejected"
    action.updated_at = datetime.utcnow()
    db.commit()
    return {"success": True, "action": _fmt(action)}
