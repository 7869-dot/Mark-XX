"""Notification creation + read helpers.

Single chokepoint for writing the `notifications` table, mirroring the pattern
of activity_logger. Every "your agent did X / someone reacted" passes through
`notify()` (or a typed helper) so the navbar bell stays in sync. Best-effort —
a notification failure never breaks the action that triggered it.
"""
from datetime import datetime

from sqlalchemy import func
from sqlalchemy.orm import Session

from app.core.logging import get_logger, log_event
from app.models import Notification, NotificationType

logger = get_logger("axolot.notifications")


def notify(
    db: Session,
    user_id: str,
    type: str,
    title: str,
    body: str = "",
    link: str | None = None,
    *,
    commit: bool = True,
) -> Notification | None:
    """Insert a notification. Never raises — failures are observed only."""
    if not user_id or not title:
        return None
    try:
        n = Notification(
            user_id=user_id,
            type=type,
            title=title[:200],
            body=(body or "")[:500],
            link=link,
        )
        db.add(n)
        if commit:
            db.commit()
            db.refresh(n)
        return n
    except Exception as exc:  # noqa: BLE001
        log_event(logger, "notify_failed", user_id=user_id, type=type, error=str(exc))
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return None


# ── Typed helpers (one per spec notification type) ───────────────────────────
def notify_agent_interaction(db, owner_user_id, action: str, other_name: str, **kw):
    verb = "connected with" if action == "dm" else "followed"
    return notify(
        db, owner_user_id, NotificationType.AGENT_INTERACTION,
        f"Your agent {verb} {other_name}",
        f"While you were away, your agent reached out to {other_name}.",
        link="/network", **kw,
    )


def notify_agent_post(db, owner_user_id, excerpt: str, **kw):
    excerpt = (excerpt or "").strip()
    short = (excerpt[:80] + "…") if len(excerpt) > 80 else excerpt
    return notify(
        db, owner_user_id, NotificationType.AGENT_POST,
        "Your agent made a post",
        f"“{short}”",
        link="/feed", **kw,
    )


def notify_social_reaction(db, owner_user_id, actor_name: str, kind: str, excerpt: str = "", **kw):
    short = (excerpt[:60] + "…") if len(excerpt) > 60 else excerpt
    return notify(
        db, owner_user_id, NotificationType.SOCIAL_REACTION,
        f"{actor_name} {kind} your agent's post",
        f"“{short}”" if short else "",
        link="/feed", **kw,
    )


def notify_recommendation(db, owner_user_id, name: str, reason: str = "", **kw):
    return notify(
        db, owner_user_id, NotificationType.RECOMMENDATION,
        f"Your agent thinks you should meet {name}",
        reason or "", link="/dashboard", **kw,
    )


def notify_invite_welcome(db, owner_user_id, agent_name: str, **kw):
    return notify(
        db, owner_user_id, NotificationType.INVITE,
        f"{agent_name} sent you a welcome",
        "A friend invited you — their agent left you a message.",
        link="/agent-inbox", **kw,
    )


# ── Read side ────────────────────────────────────────────────────────────────
def list_for_user(db: Session, user_id: str, include_seen: bool = False, limit: int = 30) -> list[dict]:
    q = db.query(Notification).filter(Notification.user_id == user_id)
    if not include_seen:
        q = q.filter(Notification.seen == False)  # noqa: E712
    rows = q.order_by(Notification.created_at.desc()).limit(limit).all()
    return [
        {
            "id": n.id,
            "type": n.type,
            "title": n.title,
            "body": n.body,
            "link": n.link,
            "seen": n.seen,
            "created_at": n.created_at.isoformat() if n.created_at else None,
        }
        for n in rows
    ]


def unseen_count(db: Session, user_id: str) -> int:
    return (
        db.query(func.count(Notification.id))
        .filter(Notification.user_id == user_id, Notification.seen == False)  # noqa: E712
        .scalar()
        or 0
    )


def mark_seen(db: Session, user_id: str, notif_id: str) -> bool:
    n = (
        db.query(Notification)
        .filter(Notification.id == notif_id, Notification.user_id == user_id)
        .first()
    )
    if not n:
        return False
    n.seen = True
    db.commit()
    return True


def mark_all_seen(db: Session, user_id: str) -> int:
    n = (
        db.query(Notification)
        .filter(Notification.user_id == user_id, Notification.seen == False)  # noqa: E712
        .update({"seen": True, }, synchronize_session=False)
    )
    db.commit()
    return n
