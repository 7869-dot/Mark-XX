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


def classify_intent(db: Session, jarvis: Agent | None, message: str) -> str:
    """Jarvis reads a free-form task and decides WHICH sub-agent owns it.

    This is the manager's core job: receive a task, pick the right sub-agent.
    Returns one of _DELEGATE_LANES. Falls back to 'self' on any failure so the
    user always gets a reply. The stub returns a deterministic keyword route so
    delegation is testable offline.
    """
    if not jarvis:
        return "self"
    try:
        from app.services.gemini import generate_for_agent, extract_json

        instruction = (
            "You are Jarvis, the manager of three sub-agents. Read the user's "
            "message and decide who should handle it:\n"
            "- \"email\": writing/replying to an email or anything inbox-related\n"
            "- \"web\": researching, finding, or looking something up on the web\n"
            "- \"schedule\": booking, calendar, or meeting-time requests\n"
            "- \"post\": drafting a social/feed post\n"
            "- \"self\": none of the above — you should just respond yourself\n\n"
            f"User message: \"{message}\"\n\n"
            "Return ONLY valid JSON: {\"lane\": \"email|web|schedule|post|self\"}. "
            "No preamble."
        )
        data = extract_json(generate_for_agent(db, jarvis, instruction, response_format="jarvis_route"))
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
    jarvis = _jarvis_agent(db, user.id)
    reply, action, follow_up = "", None, None
    delegated_to = None

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
              delegated_to=delegated_to, action=action.type if action else None)
    return JarvisChatResponse(reply=reply, mode=mode, action=action, follow_up=follow_up,
                              delegated_to=delegated_to)


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
