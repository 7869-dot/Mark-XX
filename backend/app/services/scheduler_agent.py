"""Scheduler agent — drafts calendar events from natural language (Sprint 3A).

V1 produces a structured ScheduleDraft for the user to approve. It does NOT
write to Google Calendar — real OAuth write is deferred to Sprint 4. The draft
is clearly a proposal, never a booked event.
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.logging import get_logger, log_event
from app.models import Agent, ScheduleDraft
from app.models.agent import AgentRole

logger = get_logger("axolot.scheduler_agent")


def _scheduler_agent(db: Session, user_id: str) -> Agent | None:
    """The web agent stands in as the scheduler's voice (no dedicated role).
    Falls back to Jarvis, then the feed agent — purely for voice consistency."""
    for role in (AgentRole.web, AgentRole.jarvis, AgentRole.feed):
        a = db.query(Agent).filter(
            Agent.user_id == user_id, Agent.role == role.value
        ).first()
        if a:
            return a
    return None


def draft_event(db: Session, task_description: str, user_id: str) -> ScheduleDraft | None:
    """Extract a calendar event from `task_description` and store it as a draft.
    Returns the ScheduleDraft, or None on failure. Never raises into the caller."""
    agent = _scheduler_agent(db, user_id)
    if not agent:
        return None

    now_iso = datetime.utcnow().isoformat()
    instruction = (
        f"The user said: \"{task_description}\".\n"
        f"Current UTC time: {now_iso}.\n"
        "Extract a calendar event. Return ONLY valid JSON with keys: "
        "title (short), proposed_datetime (ISO 8601 or null if unspecified), "
        "duration_minutes (int or null), attendees_hint (list of names/roles, "
        "may be empty), notes (one line). No preamble."
    )
    try:
        from app.services.gemini import generate_for_agent

        raw = generate_for_agent(db, agent, instruction, response_format="schedule_draft")
        data = json.loads(raw)
    except Exception as exc:  # noqa: BLE001
        log_event(logger, "schedule_draft_failed", user_id=user_id, error=str(exc))
        return None

    dt = None
    raw_dt = data.get("proposed_datetime")
    if raw_dt:
        try:
            dt = datetime.fromisoformat(str(raw_dt).replace("Z", "+00:00").replace("+00:00", ""))
        except (ValueError, TypeError):
            dt = None

    draft = ScheduleDraft(
        user_id=user_id,
        title=str(data.get("title", "")).strip()[:500] or "Untitled event",
        proposed_datetime=dt,
        duration_minutes=_safe_int(data.get("duration_minutes")),
        attendees_hint=[str(a)[:80] for a in (data.get("attendees_hint") or [])][:10],
        notes=str(data.get("notes", "")).strip(),
        approved=None,
    )
    db.add(draft)
    db.commit()
    db.refresh(draft)
    log_event(logger, "schedule_draft_created", user_id=user_id, draft_id=draft.id)
    return draft


def _safe_int(v) -> int | None:
    try:
        return int(v) if v is not None else None
    except (TypeError, ValueError):
        return None
