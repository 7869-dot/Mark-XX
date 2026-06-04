"""Jarvis routing layer (Sprint 3A).

A single entry — route_chat() — interprets a user message under a ChatMode and
either talks back directly (DEFAULT) or routes to a sub-agent and frames the
result. Jarvis ALWAYS speaks in the reply; the user never feels like they
switched apps. Every external-effect mode returns a draft requiring approval.
"""
from __future__ import annotations

import json

from sqlalchemy.orm import Session

from app.core.logging import get_logger, log_event
from app.models import Agent, ChatHistory, PostDraft
from app.models.agent import AgentRole
from app.schemas.jarvis import (
    ChatMode, JarvisAction, JarvisChatResponse, AgentTask,
)

logger = get_logger("axolot.jarvis_router")


def _jarvis_agent(db: Session, user_id: str) -> Agent | None:
    for role in (AgentRole.jarvis, AgentRole.feed):
        a = db.query(Agent).filter(Agent.user_id == user_id, Agent.role == role.value).first()
        if a:
            return a
    return None


def _posting_agent(db: Session, user_id: str) -> Agent | None:
    return db.query(Agent).filter(
        Agent.user_id == user_id, Agent.role == AgentRole.feed.value
    ).first()


def _frame(db: Session, jarvis: Agent | None, instruction: str, fallback: str) -> str:
    """A short in-character Jarvis line framing a sub-agent's output."""
    if not jarvis:
        return fallback
    try:
        from app.services.gemini import generate_for_agent

        text = (generate_for_agent(db, jarvis, instruction, response_format="jarvis_frame") or "").strip().strip('"')
        return text or fallback
    except Exception:  # noqa: BLE001
        return fallback


# Lanes Jarvis can delegate a free-form task to. "self" = Jarvis answers directly.
_DELEGATE_LANES = ("email", "web", "schedule", "post", "self")
_LANE_TO_MODE = {
    "email": ChatMode.EMAIL,
    "web": ChatMode.RESEARCH,     # the web/research sub-agent
    "schedule": ChatMode.SCHEDULE,
    "post": ChatMode.POST,
    "self": ChatMode.DEFAULT,
}


# Explicit-command keywords -> lane. Checked first: a fast, reliable route that
# CAN'T be drowned out by persona context the way the model classifier was.
# Email/schedule are checked before web so "email Dana to schedule…" -> email.
_LANE_KEYWORDS: dict[str, tuple[str, ...]] = {
    "email": (
        "email", "e-mail", "inbox", "reply to", "respond to", "draft a reply",
        "draft an email", "draft email", "write an email", "send an email",
        "send a note", "message to", "reach out to", "follow up with",
    ),
    "schedule": (
        "schedule a", "schedule the", "book a", "set up a meeting", "set up a call",
        "find a time", "add to my calendar", "put on my calendar", "calendar",
        "what's on my calendar", "my schedule",
    ),
    "web": (
        "find me", "find a", "search for", "search the", "look up", "look into",
        "look for", "research", "what's happening", "whats happening",
        "what is happening", "latest news", "news on", "news about", "find out",
        "tell me about", "look it up", "google",
    ),
}


def _keyword_lane(message: str) -> str | None:
    m = (message or "").lower()
    for lane in ("email", "schedule", "web"):
        if any(kw in m for kw in _LANE_KEYWORDS[lane]):
            return lane
    return None


def classify_intent(db: Session, jarvis: Agent | None, message: str) -> str:
    """Jarvis reads a free-form task and decides WHICH sub-agent owns it.

    Returns one of _DELEGATE_LANES. An explicit-command keyword wins immediately
    (fast, reliable). Otherwise a LEAN model call decides — deliberately NOT via
    generate_for_agent: feeding the routing question 6k chars of persona/memory
    made the model default to "self" on almost everything (the bug). Falls back
    to "self" on any failure so the user always gets a reply.
    """
    kw = _keyword_lane(message)
    if kw:
        log_event(logger, "jarvis_route_keyword", lane=kw)
        return kw
    if not jarvis:
        return "self"
    try:
        from app.services.gemini import generate, extract_json

        instruction = (
            "Classify the user's message into exactly one lane and output ONLY JSON.\n"
            "- email: writing, replying to, or triaging email / the inbox\n"
            "- web: finding, searching, researching, or looking anything up online\n"
            "- schedule: booking, calendar, or meeting-time requests\n"
            "- post: drafting a social post\n"
            "- self: ONLY pure conversation, opinion, or thinking-out-loud that needs no tool\n\n"
            "Prefer a tool lane whenever the user asks to DO or FIND something; use "
            "self only for open-ended reflection.\n\n"
            f"User message: \"{message}\"\n\n"
            "Return ONLY: {\"lane\": \"email|web|schedule|post|self\"}"
        )
        data = extract_json(generate(instruction, response_format="jarvis_route"))
        lane = str(data.get("lane", "self")).strip().lower()
        return lane if lane in _DELEGATE_LANES else "self"
    except Exception:  # noqa: BLE001
        return "self"


def route_chat(db: Session, user, message: str, mode: ChatMode, context: dict | None = None) -> JarvisChatResponse:
    """Route one chat turn. Persists the exchange to ChatHistory (tagged with
    mode) so it feeds the existing summary/personality pipeline.

    mode=AUTO is the manager flow: Jarvis classifies the task and delegates to
    the correct sub-agent, then the resolved lane runs exactly as if the user
    had picked that mode."""
    # Self-heal the team so Jarvis always has a body to delegate through — a user
    # can hit chat before the login briefing has seeded the agents (or on a legacy
    # account). Without this, delegation silently collapses to "self".
    from app.services.agent_team import ensure_team

    try:
        ensure_team(db, user)
    except Exception as exc:  # noqa: BLE001
        log_event(logger, "route_chat_ensure_team_failed", user_id=user.id, error=str(exc))

    jarvis = _jarvis_agent(db, user.id)
    reply, action, follow_up = "", None, None
    delegated_to = None

    # The manager remembers: persist any durable interest/goal the user voiced so
    # the web scout can act on it later (the "Jarvis tracks your interests" loop).
    from app.services import user_profile as profiles

    remembered = profiles.remember_signals(db, user, message)

    # AUTO: Jarvis itself decides which sub-agent owns the task.
    if mode == ChatMode.AUTO:
        lane = classify_intent(db, jarvis, message)
        delegated_to = lane
        mode = _LANE_TO_MODE[lane]
        log_event(logger, "jarvis_delegated", user_id=user.id, lane=lane)

    if mode == ChatMode.DEFAULT:
        reply = _default_reply(db, jarvis, message)

    elif mode == ChatMode.EMAIL:
        from app.services.email_agent import execute_task

        result = execute_task(db, AgentTask(agent_role="email", task_description=message, priority="today"), user.id)
        if result:
            action = JarvisAction(
                type="draft_email",
                payload={
                    "draft_id": result.id,
                    "subject_line": result.subject_line,
                    "recipient_hint": result.recipient_hint,
                    "draft_content": result.draft_content,
                },
                requires_approval=True,
            )
            reply = _frame(
                db, jarvis,
                f"You asked me to handle this email: \"{message}\". I drafted it. "
                "In ONE short, in-character sentence, tell the user it's ready to review (not sent).",
                "Done — drafted something that sounds like you. Check it before it goes.",
            )
        else:
            reply = "Couldn't draft that one — want to give me a bit more on who it's for?"

    elif mode == ChatMode.SCHEDULE:
        from app.services.scheduler_agent import draft_event

        draft = draft_event(db, message, user.id)
        if draft:
            action = JarvisAction(
                type="schedule_event",
                payload={
                    "draft_id": draft.id,
                    "title": draft.title,
                    "proposed_datetime": draft.proposed_datetime.isoformat() if draft.proposed_datetime else None,
                    "duration_minutes": draft.duration_minutes,
                    "attendees_hint": draft.attendees_hint or [],
                    "notes": draft.notes,
                },
                requires_approval=True,
            )
            reply = _frame(
                db, jarvis,
                f"You asked to schedule: \"{message}\". I drafted the event (not booked yet). "
                "In ONE short, in-character sentence, tell the user it's a draft to confirm.",
                "Drafted it — it's a proposal, not booked. Confirm and I'll hold the slot.",
            )
        else:
            reply = "I couldn't pin that down — when and with whom?"

    elif mode == ChatMode.RESEARCH:
        from app.services.research_agent import research

        result = research(db, message, user.id)
        action = JarvisAction(type="research_result", payload=result, requires_approval=False)
        reply = result["synthesis"]
        fu = result.get("follow_up_questions") or []
        follow_up = fu[0] if fu else None

    elif mode == ChatMode.POST:
        content, island_hint = _draft_post(db, jarvis or _posting_agent(db, user.id), message)
        draft = PostDraft(user_id=user.id, content=content, island_hint=island_hint, approved=None)
        db.add(draft)
        db.commit()
        db.refresh(draft)
        action = JarvisAction(
            type="post_draft",
            payload={"draft_id": draft.id, "content": draft.content, "island_hint": draft.island_hint},
            requires_approval=True,
        )
        reply = _frame(
            db, jarvis,
            f"The user wants to post about: \"{message}\". I drafted it in their voice. "
            "In ONE short, in-character sentence, ask if it's the right vibe or wants it sharper.",
            "Here's a draft — sounds like you on a good day. Want it sharper, or is this the vibe?",
        )

    # Persist the exchange into ChatHistory (mode-tagged) so it feeds memory.
    db.add(ChatHistory(user_id=user.id, role="user", content=message, mode=mode.value))
    db.add(ChatHistory(user_id=user.id, role="agent", content=reply, mode=mode.value))
    db.commit()

    log_event(logger, "jarvis_chat", user_id=user.id, mode=mode.value,
              delegated_to=delegated_to, action=action.type if action else None,
              remembered=remembered)
    return JarvisChatResponse(reply=reply, mode=mode, action=action, follow_up=follow_up,
                              delegated_to=delegated_to, remembered_interests=remembered)


def _default_reply(db: Session, jarvis: Agent | None, message: str) -> str:
    if not jarvis:
        return "I'm here. What's on your mind?"
    try:
        from app.services.gemini import generate_for_agent

        instruction = (
            "Your user is thinking out loud with you. Respond in 1-3 sentences, in "
            "their voice — pressure-test, push back, or build on it. Never "
            "sycophantic, never an assistant. Their message:\n" + message
        )
        return (generate_for_agent(db, jarvis, instruction, response_format="text") or "").strip() or "Say more."
    except Exception:  # noqa: BLE001
        return "Say more — I'm following."


def _draft_post(db: Session, agent: Agent | None, message: str) -> tuple[str, str]:
    if not agent:
        return message.strip(), ""
    try:
        from app.services.gemini import generate_for_agent, extract_json

        instruction = (
            f"The user wants to post this idea: \"{message}\". Draft a short social "
            "post in THEIR voice (not generic social copy). Return ONLY valid JSON "
            "with keys: content (the post), island_hint (a topic/community it fits, "
            "or empty string). No preamble."
        )
        data = extract_json(generate_for_agent(db, agent, instruction, response_format="post_draft_mode"))
        return (str(data.get("content", "")).strip() or message.strip(), str(data.get("island_hint", "")).strip()[:200])
    except Exception:  # noqa: BLE001
        return message.strip(), ""
