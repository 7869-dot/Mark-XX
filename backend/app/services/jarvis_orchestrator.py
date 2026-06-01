"""Jarvis wake-up loop — the manager agent activating on login.

On authentication, Jarvis pulls the user's state (personality, recent
conversation summaries, last email-triage signal, upcoming calendar), reasons
*as the Jarvis agent* (so its persona/system_prompt + the user's voice are
injected via the existing context_builder), and returns a JarvisContext:
a specific greeting, one sharp question, internal notes about the user, and a
team briefing of tasks assigned to the email/wildcard agents.

Cached in the in-memory TTL cache (30 min) keyed by user_id — regenerated only
on first session login or manual refresh, never on every page paint.
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.cache import cache
from app.core.logging import get_logger, log_event
from app.models import (
    Agent, ConversationSummary, UserPersonality, ClassifiedEmail, User,
)
from app.models.agent import AgentRole
from app.schemas.jarvis import JarvisContext, AgentTask

logger = get_logger("axolot.jarvis")

CACHE_TTL_SECONDS = 30 * 60


def _cache_key(user_id: str) -> str:
    return f"jarvis_ctx:{user_id}"


def get_jarvis_agent(db: Session, user_id: str) -> Agent | None:
    """The user's Jarvis agent — self-heals the team if it's somehow missing."""
    agent = (
        db.query(Agent)
        .filter(Agent.user_id == user_id, Agent.role == AgentRole.jarvis.value)
        .first()
    )
    if agent:
        return agent
    # Risk-flag #2: first-ever login race / legacy account — seed the team now.
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None
    try:
        from app.services.agent_team import ensure_team

        ensure_team(db, user)
    except Exception as exc:  # noqa: BLE001
        log_event(logger, "jarvis_ensure_team_failed", user_id=user_id, error=str(exc))
        return None
    return (
        db.query(Agent)
        .filter(Agent.user_id == user_id, Agent.role == AgentRole.jarvis.value)
        .first()
    )


def _build_context_bundle(db: Session, user: User, jarvis: Agent) -> dict:
    personality = (
        db.query(UserPersonality).filter(UserPersonality.user_id == user.id).first()
    )
    summaries = (
        db.query(ConversationSummary)
        .filter(ConversationSummary.user_id == user.id)
        .order_by(ConversationSummary.created_at.desc())
        .limit(3)
        .all()
    )
    # Last email-triage signal (best-effort; the email store is the classifier's).
    recent_emails = (
        db.query(ClassifiedEmail)
        .filter(ClassifiedEmail.user_id == user.id)
        .order_by(ClassifiedEmail.created_at.desc())
        .limit(5)
        .all()
    )
    # Upcoming calendar — skip gracefully if no OAuth.
    upcoming = "Calendar not connected."
    if getattr(user, "calendar_connected", False):
        try:
            from app.services.calendar_service import get_upcoming_summary

            upcoming = get_upcoming_summary(db, user.id, days=2) or "Nothing on the calendar."
        except Exception:  # noqa: BLE001
            upcoming = "Calendar unavailable."

    return {
        "user_name": user.name,
        "goals": user.goals or [],
        "personality": {
            "communication_style": (personality.communication_style if personality else "") or "",
            "interests": (personality.interests if personality else []) or [],
            "notes": (personality.notes if personality else "") or "",
        },
        "recent_conversation_summaries": [s.summary for s in summaries],
        "email_signal": [
            {
                "subject": e.subject,
                "category": e.category.value if hasattr(e.category, "value") else e.category,
                "from": e.sender,
            }
            for e in recent_emails
        ],
        "upcoming_calendar": upcoming,
    }


_INSTRUCTION = """It's a new session. Brief your user as their manager — their sharper subconscious.

Their current state:
{bundle}

Return ONLY valid JSON (no preamble, no markdown) with exactly these keys:
- "greeting": 1-2 sentences, SPECIFIC to them today (reference something real from the state). Never "Good morning", never "How can I help", never productivity metrics.
- "question": ONE sharp question — something they've been avoiding or haven't addressed. Make it feel like it came from inside their own head.
- "known_about_user": 3-5 short first-person internal notes (e.g. "Still hasn't resolved the pitch deck."). Observations, not announcements.
- "team_briefing": a list of tasks you're assigning. Each: {{"agent_role": "email" | "wildcard", "task_description": "...", "priority": "now"|"today"|"this_week"}}. Be direct, like instructions to your team. Assign email tasks only when there's a real thread to act on.

No "posting" tasks — the public voice stays user-driven."""


def _coerce_context(raw: str) -> JarvisContext:
    data = json.loads(raw)
    tasks = []
    for t in (data.get("team_briefing") or []):
        role = str(t.get("agent_role", "")).lower()
        if role not in ("email", "wildcard"):
            continue  # Jarvis never assigns to posting; drop anything else.
        try:
            tasks.append(AgentTask(
                agent_role=role,
                task_description=str(t.get("task_description", "")).strip(),
                priority=t.get("priority", "today") if t.get("priority") in ("now", "today", "this_week") else "today",
                status="pending",
            ))
        except Exception:  # noqa: BLE001
            continue
    return JarvisContext(
        greeting=str(data.get("greeting", "")).strip(),
        question=str(data.get("question", "")).strip(),
        known_about_user=[str(x).strip() for x in (data.get("known_about_user") or []) if str(x).strip()][:5],
        team_briefing=tasks,
        timestamp=datetime.utcnow(),
    )


def wake_up(db: Session, user_id: str, *, force: bool = False) -> JarvisContext | None:
    """Generate (or return cached) JarvisContext for the user. Never raises —
    returns None on failure so the home screen degrades gracefully."""
    if not force:
        cached = cache.get(_cache_key(user_id))
        if cached is not None:
            return cached

    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        return None
    jarvis = get_jarvis_agent(db, user_id)
    if not jarvis:
        return None

    try:
        from app.services.gemini import generate_for_agent

        bundle = _build_context_bundle(db, user, jarvis)
        instruction = _INSTRUCTION.format(bundle=json.dumps(bundle, default=str))
        raw = generate_for_agent(db, jarvis, instruction, response_format="jarvis_context")
        ctx = _coerce_context(raw)
        if not ctx.greeting:
            return None
    except Exception as exc:  # noqa: BLE001
        log_event(logger, "jarvis_wake_up_failed", user_id=user_id, error=str(exc))
        return None

    cache.set(_cache_key(user_id), ctx, ttl_seconds=CACHE_TTL_SECONDS)

    # Dispatch the email tasks Jarvis assigned (best-effort, async-safe: this is
    # already off the login hot path — the endpoint calls wake_up directly).
    try:
        from app.services.email_agent import execute_task

        for task in ctx.team_briefing:
            if task.agent_role == "email":
                execute_task(db, task, user_id)
    except Exception as exc:  # noqa: BLE001
        log_event(logger, "jarvis_dispatch_failed", user_id=user_id, error=str(exc))

    log_event(logger, "jarvis_woke_up", user_id=user_id, tasks=len(ctx.team_briefing))
    return ctx
