"""Nudge engine — periodic per-user proactivity job.

Runs every NUDGE_SCHEDULE_MINUTES.  For each user with a valid OAuth token it
checks for new triggers and writes Nudge rows.

Rate cap: at most NUDGE_RATE_CAP nudges per user per day.
Quiet hours: no nudges between NUDGE_QUIET_HOURS_START and NUDGE_QUIET_HOURS_END (UTC).
TODO: per-user timezone support (currently UTC).
"""
from __future__ import annotations

import logging
from datetime import datetime, timezone, timedelta

from auth import get_valid_access_token
from config import (
    NUDGE_RATE_CAP,
    NUDGE_QUIET_HOURS_START,
    NUDGE_QUIET_HOURS_END,
)
from db import SessionLocal
from models import Nudge, OAuthToken, User
from tools import gmail_tools, calendar_tools

logger = logging.getLogger(__name__)


def _in_quiet_hours() -> bool:
    hour = datetime.now(timezone.utc).hour
    if NUDGE_QUIET_HOURS_START > NUDGE_QUIET_HOURS_END:
        # spans midnight: quiet from 22 to 8
        return hour >= NUDGE_QUIET_HOURS_START or hour < NUDGE_QUIET_HOURS_END
    return NUDGE_QUIET_HOURS_END <= hour < NUDGE_QUIET_HOURS_START


def _today_nudge_count(db, user_id: str) -> int:
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        db.query(Nudge)
        .filter(
            Nudge.user_id == user_id,
            Nudge.created_at >= today_start,
        )
        .count()
    )


def _already_nudged(db, user_id: str, type: str, key: str) -> bool:
    """Check if we already sent a nudge of this type with this key today."""
    today_start = datetime.now(timezone.utc).replace(hour=0, minute=0, second=0, microsecond=0)
    return (
        db.query(Nudge)
        .filter(
            Nudge.user_id == user_id,
            Nudge.type == type,
            Nudge.message.contains(key),
            Nudge.created_at >= today_start,
        )
        .first()
    ) is not None


def _write_nudge(db, user_id: str, type: str, message: str) -> str:
    nudge = Nudge(user_id=user_id, type=type, message=message)
    db.add(nudge)
    db.flush()
    return nudge.id


async def run_nudge_cycle(user_id: str, db) -> list[str]:
    """
    Check triggers for user_id and write Nudge rows if warranted.
    Returns list of created nudge IDs.
    """
    if _in_quiet_hours():
        return []

    today_count = _today_nudge_count(db, user_id)
    if today_count >= NUDGE_RATE_CAP:
        return []

    # Get access token — skip users without OAuth
    try:
        access_token = await get_valid_access_token(user_id, db)
    except ValueError:
        return []

    created_ids: list[str] = []
    remaining = NUDGE_RATE_CAP - today_count

    # ── Trigger 1: imminent calendar events (next 30 min) ─────────────────────
    try:
        imminent = calendar_tools.get_imminent_events(access_token, within_minutes=30)
        for event in imminent[:2]:
            key = event.get("summary", "")[:40]
            if not _already_nudged(db, user_id, "calendar", key):
                nid = _write_nudge(
                    db, user_id, "calendar",
                    f"Upcoming in 30 min: {event['summary']} "
                    f"(starts {event['start']})"
                    + (f" — {len(event['attendees'])} attendees" if event["attendees"] else ""),
                )
                created_ids.append(nid)
                remaining -= 1
                if remaining <= 0:
                    break
    except Exception as exc:
        logger.debug("Calendar nudge check failed for user %s: %s", user_id, exc)

    if remaining <= 0:
        db.commit()
        return created_ids

    # ── Trigger 2: new important unread emails ─────────────────────────────────
    try:
        # Emails received in the last nudge window
        recent_emails = gmail_tools.list_recent_emails(
            access_token,
            max_results=5,
            query="is:unread newer_than:30m",
        )
        if recent_emails:
            senders = ", ".join(
                e.get("from", "").split("<")[0].strip()
                for e in recent_emails[:3]
            )
            key = senders[:40]
            if not _already_nudged(db, user_id, "email", key):
                count = len(recent_emails)
                nid = _write_nudge(
                    db, user_id, "email",
                    f"{'New email' if count == 1 else f'{count} new emails'} "
                    f"from {senders}."
                    + (" Check your inbox." if count > 1 else ""),
                )
                created_ids.append(nid)
                remaining -= 1
    except Exception as exc:
        logger.debug("Email nudge check failed for user %s: %s", user_id, exc)

    if remaining <= 0:
        db.commit()
        return created_ids

    # ── Trigger 3: new unseen connection briefings ─────────────────────────────
    try:
        from models import Briefing  # avoid circular at module level
        unseen_count = (
            db.query(Briefing)
            .filter_by(user_id=user_id, seen=False)
            .count()
        )
        if unseen_count:
            key = f"connection match"
            if not _already_nudged(db, user_id, "connection", key):
                verb = "is" if unseen_count == 1 else "are"
                subj = "A new connection match" if unseen_count == 1 else f"{unseen_count} new connection matches"
                nid = _write_nudge(
                    db, user_id, "connection",
                    f"{subj} {verb} waiting for your review.",
                )
                created_ids.append(nid)
    except Exception as exc:
        logger.debug("Connection nudge check failed for user %s: %s", user_id, exc)

    db.commit()
    return created_ids


async def run_all() -> None:
    """Run the nudge cycle for all users. Called by APScheduler."""
    if _in_quiet_hours():
        logger.debug("Nudge engine: quiet hours — skipping")
        return

    db = SessionLocal()
    try:
        users = db.query(User).all()
        total = 0
        for user in users:
            try:
                ids = await run_nudge_cycle(user.id, db)
                total += len(ids)
            except Exception as exc:
                logger.warning("Nudge cycle error for user %s: %s", user.id, exc)
        if total:
            logger.info("Nudge engine: wrote %d nudge(s) across %d users", total, len(users))
    finally:
        db.close()
