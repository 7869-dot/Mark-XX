"""Notification feed for the navbar bell."""
from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.api.envelope import envelope
from app.core.db import get_db
from app.core.ratelimit import limiter
from app.core.security import get_current_user
from app.models import User
from app.services import notifications

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("")
@limiter.limit("120/minute")  # 30s poll per client leaves generous headroom
def list_notifications(
    request: Request,
    include_seen: bool = False,
    limit: int = 30,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Unseen notifications (newest first) + the unseen badge count."""
    items = notifications.list_for_user(
        db, user.id, include_seen=include_seen, limit=min(max(limit, 1), 50)
    )
    return envelope({"items": items, "unseen_count": notifications.unseen_count(db, user.id)})


@router.post("/{notif_id}/seen")
def mark_seen(
    notif_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    ok = notifications.mark_seen(db, user.id, notif_id)
    return envelope({"seen": ok, "id": notif_id})


@router.post("/seen-all")
def mark_all_seen(
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    n = notifications.mark_all_seen(db, user.id)
    return envelope({"marked_seen": n})
