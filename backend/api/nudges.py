"""Nudges endpoints.

GET  /nudges           — list undismissed nudges for the user
POST /nudges/{id}/dismiss — dismiss a nudge
"""
from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from api.deps import current_user_id
from db import get_db
from models import Nudge

router = APIRouter(prefix="/nudges", tags=["nudges"])


def _fmt(n: Nudge) -> dict:
    return {
        "id":         n.id,
        "type":       n.type,
        "message":    n.message,
        "dismissed":  n.dismissed,
        "created_at": n.created_at.isoformat() if n.created_at else "",
    }


@router.get("")
async def list_nudges(
    uid: str = Depends(current_user_id),
    db:  Session = Depends(get_db),
    include_dismissed: bool = False,
):
    """Return nudges for the user. By default only undismissed nudges."""
    q = db.query(Nudge).filter_by(user_id=uid)
    if not include_dismissed:
        q = q.filter_by(dismissed=False)
    nudges = q.order_by(Nudge.created_at.desc()).limit(50).all()
    return [_fmt(n) for n in nudges]


@router.post("/{nudge_id}/dismiss")
async def dismiss_nudge(
    nudge_id: str,
    uid: str = Depends(current_user_id),
    db:  Session = Depends(get_db),
):
    nudge = db.query(Nudge).filter_by(id=nudge_id, user_id=uid).first()
    if not nudge:
        raise HTTPException(status_code=404, detail="Nudge not found.")
    nudge.dismissed = True
    db.commit()
    return {"success": True, "nudge": _fmt(nudge)}
