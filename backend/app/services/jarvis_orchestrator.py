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
- "team_briefing": a list of tasks you're assigning. Each: {{"agent_role": "email" | "web", "task_description": "...", "priority": "now"|"today"|"this_week"}}. Be direct, like instructions to your team. Assign email tasks only when there's a real thread to act on; assign web tasks to scout opportunities tied to their goals.

No "feed" tasks — the public voice stays user-driven."""


def _coerce_context(raw: str) -> JarvisContext:
    data = json.loads(raw)
    tasks = []
    for t in (data.get("team_briefing") or []):
        role = str(t.get("agent_role", "")).lower()
        if role not in ("email", "web"):
            continue  # Jarvis never assigns to feed; drop anything else.
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


# ── Session orchestration (Section 4) ────────────────────────────────────────
def _first_name(user: User) -> str:
    return (user.name or "there").split(" ")[0]


def _synthesise(db: Session, jarvis: Agent | None, user: User, reports: dict) -> dict:
    """Fold the three sub-agent reports into one briefing + 3 action items, in
    the user's voice. Heavy/ultra tier; degrades to a deterministic summary."""
    from app.services import user_profile as profiles

    profile = profiles.get_profile(db, user.id)
    jarvis_persona = profiles.build_jarvis_prompt(profile, _first_name(user))
    instruction = (
        jarvis_persona
        + "\n\nIt's a new session. Your three sub-agents just reported. Synthesise "
        "their reports into ONE briefing spoken to the user in their voice — lead "
        "with what matters, skip the obvious, never dump raw data. Then propose "
        "exactly 3 concrete action items.\n\n"
        f"email_agent report: {json.dumps(reports.get('email', {}), default=str)}\n"
        f"feed_agent report: {json.dumps(reports.get('feed', {}), default=str)}\n"
        f"web_agent report: {json.dumps(reports.get('web', {}), default=str)}\n\n"
        "Return ONLY valid JSON: {\"briefing\": \"<2-5 sentences>\", "
        "\"action_items\": [\"<item>\", \"<item>\", \"<item>\"]}. No preamble."
    )
    briefing, action_items = "", []
    if jarvis:
        try:
            from app.services.gemini import generate_for_agent

            raw = generate_for_agent(db, jarvis, instruction, response_format="jarvis_session")
            data = json.loads(raw)
            briefing = str(data.get("briefing", "")).strip()
            action_items = [str(a).strip() for a in (data.get("action_items") or []) if str(a).strip()][:3]
        except Exception as exc:  # noqa: BLE001
            log_event(logger, "jarvis_synthesis_failed", user_id=user.id, error=str(exc))

    if not briefing:
        # Deterministic fallback so the home screen always has a briefing.
        em = reports.get("email", {})
        web = reports.get("web", {})
        bits = []
        counts = em.get("counts", {})
        if counts.get("urgent"):
            bits.append(f"{counts['urgent']} urgent email(s) need you")
        finds = web.get("top_finds", [])
        if finds:
            bits.append(f"{len(finds)} new opportunities I scouted")
        if reports.get("feed", {}).get("drafted_post"):
            bits.append("a feed post drafted and waiting")
        briefing = (
            "Here's where things stand: " + ", ".join(bits) + "."
            if bits else "Quiet since last time — nothing urgent. What do you want to focus on today?"
        )
    if not action_items:
        action_items = _fallback_actions(reports)
    return {"briefing": briefing, "action_items": action_items}


def _fallback_actions(reports: dict) -> list[str]:
    items: list[str] = []
    if reports.get("email", {}).get("action_required"):
        items.append("Clear the emails that need action")
    finds = reports.get("web", {}).get("top_finds", [])
    if finds:
        items.append(f"Look at the top opportunity: {finds[0]['title']}")
    if reports.get("feed", {}).get("drafted_post"):
        items.append("Review and approve the drafted feed post")
    while len(items) < 3:
        items.append("Tell me what to prioritise today")
    return items[:3]


def run_session(db: Session, user: User, *, force: bool = False) -> dict:
    """Section 4 orchestration. On first session (no Jarvis onboarding) returns
    an onboarding payload instead of running the sub-agents. Otherwise triggers
    all three sub-agents, synthesises a briefing + 3 action items, and returns
    everything the home screen needs. Never raises."""
    from app.services import user_profile as profiles
    from app.services.agent_team import ensure_team
    from app.services import email_agent, feed_agent, web_agent
    from app.services.agent_runs import last_runs

    ensure_team(db, user)
    profile = profiles.get_or_create_profile(db, user)
    first = _first_name(user)

    # First-interaction flow — onboard before acting as manager.
    if not profile.onboarding_complete:
        log_event(logger, "jarvis_session_onboarding", user_id=user.id)
        return {
            "onboarding": True,
            "greeting": (
                f"Hey {first} — good to finally meet you properly. Before I start "
                "running things for you, I want to actually get you. Five quick questions."
            ),
            "questions": profiles.ONBOARDING_QUESTIONS,
        }

    jarvis = get_jarvis_agent(db, user.id)

    reports: dict = {}
    for name, fn in (("email", email_agent.run_report), ("feed", feed_agent.run_report),
                     ("web", web_agent.run_report)):
        try:
            reports[name] = fn(db, user)
        except Exception as exc:  # noqa: BLE001
            log_event(logger, "jarvis_subagent_failed", user_id=user.id, agent=name, error=str(exc))
            reports[name] = {"error": True}

    synthesis = _synthesise(db, jarvis, user, reports)
    status = _status_payload(last_runs(db, user.id))

    log_event(logger, "jarvis_session_ran", user_id=user.id)
    return {
        "onboarding": False,
        "greeting": f"Welcome back, {first}.",
        "briefing": synthesis["briefing"],
        "action_items": synthesis["action_items"],
        "reports": reports,
        "agent_status": status,
        "focus_prompt": "What do you want to focus on today?",
    }


def _status_payload(runs: dict) -> list[dict]:
    out = []
    for name, row in runs.items():
        out.append({
            "agent_name": name,
            "last_run": row.ran_at.isoformat() if row else None,
            "last_summary": row.report_summary if row else None,
            "status": row.status if row else "idle",
        })
    return out
