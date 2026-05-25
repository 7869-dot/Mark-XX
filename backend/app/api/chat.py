"""Conversational chat between a user and their own agent.

Persists turns to ChatHistory (the existing memory pipeline owns summarization
and personality derivation downstream — this router only appends turns).
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.core.ratelimit import limiter
from app.models import User, ChatHistory
from app.api.envelope import envelope
from app.prompts.templates import CHAT_CONVERSATION
from app.services.context_builder import build_agent_context
from app.services import gemini
from app.services.active_agent import resolve_active_agent
from app.services.agent_service import create_agent_for_user
from app.services.agent_tools import build_agent_tools
from app.memory.summarizer import summarize_user
from app.memory.personality_tracker import refresh_personality_if_due
from app.services.activity_logger import log_activity
from app.models import ActivityType

# Appended to the chat prompt when the agent has live Gmail/Calendar tools, so
# it reaches for real data instead of inventing email/event details.
_TOOL_SYSTEM_NOTE = (
    "\n\nYou have live, authorized access to this user's Gmail and Google "
    "Calendar through tools. When the user asks anything about their email or "
    "schedule, CALL THE TOOLS to fetch real data before answering — never "
    "invent email or event details. Summarize tool results conversationally."
)

router = APIRouter(prefix="/chat", tags=["chat"])


class ChatMessageIn(BaseModel):
    # Hard ceiling protects Gemini token cost + the prompt-injection surface.
    message: str = Field(..., min_length=1, max_length=4000)


def _serialize(m: ChatHistory) -> dict:
    return {
        "id": m.id,
        "role": m.role,
        "content": m.content,
        "created_at": m.created_at.isoformat(),
    }


@router.get("/history")
def history(limit: int = 100, db: Session = Depends(get_db),
            user: User = Depends(get_current_user)):
    rows = (
        db.query(ChatHistory)
        .filter(ChatHistory.user_id == user.id)
        .order_by(ChatHistory.created_at.desc())
        .limit(limit)
        .all()
    )
    rows.reverse()
    return envelope(
        {"messages": [_serialize(m) for m in rows]},
        agent_id=user.agent.id if user.agent else None,
    )


@router.post("/message")
@limiter.limit("30/minute")
def message(request: Request, body: ChatMessageIn, background_tasks: BackgroundTasks,
            db: Session = Depends(get_db),
            user: User = Depends(get_current_user)):
    text = body.message.strip()
    if not text:
        raise HTTPException(status_code=400, detail="message is required")

    # Multi-agent: X-Agent-Id selects which of the user's agents speaks. Falls
    # back to primary. resolve_active_agent enforces ownership and raises 403
    # for an invalid header.
    x_agent_id = request.headers.get("X-Agent-Id")
    agent = resolve_active_agent(db, user, x_agent_id)
    if not agent:
        create_agent_for_user(db, user)
        db.refresh(user)
        agent = resolve_active_agent(db, user, x_agent_id)

    user_turn = ChatHistory(user_id=user.id, role="user", content=text)
    db.add(user_turn)
    db.commit()

    ctx = build_agent_context(db, agent)
    prompt = CHAT_CONVERSATION.format(user_message=text, **ctx)

    # If the user has connected Gmail/Calendar, hand the agent the tool layer so
    # it can act on real inbox/schedule data autonomously.
    tools = build_agent_tools(db, user)
    if tools:
        reply = (
            gemini.generate_with_tools(prompt + _TOOL_SYSTEM_NOTE, tools, hint=text)
            or ""
        ).strip()
    else:
        reply = (gemini.generate(prompt, response_format="text") or "").strip()
    if not reply:
        reply = "I'm here, but I couldn't form a response just now. Try again?"

    agent_turn = ChatHistory(user_id=user.id, role="agent", content=reply)
    db.add(agent_turn)
    db.commit()
    db.refresh(agent_turn)

    # Log to the activity feed so the dashboard shows what the agent did.
    log_activity(
        db, agent.id, ActivityType.chat_handled,
        f"Handled a chat turn from {user.name}.",
        metadata={"chars": len(text)},
    )

    # Compress the conversation into ConversationSummary off the response path,
    # then every 5 user turns also re-derive the long-term UserPersonality.
    background_tasks.add_task(summarize_user, user.id)
    background_tasks.add_task(refresh_personality_if_due, user.id)

    # Seed the structured speech-mirror profile once the user has enough
    # messages. Cheap, no LLM — runs every turn but no-ops after the first
    # successful bootstrap.
    def _bootstrap(user_id: str):
        from app.core.db import SessionLocal
        from app.services.speech_profile import bootstrap_from_first_messages
        _db = SessionLocal()
        try:
            bootstrap_from_first_messages(_db, user_id)
        finally:
            _db.close()
    background_tasks.add_task(_bootstrap, user.id)

    return envelope(
        {"reply": _serialize(agent_turn), "echo": _serialize(user_turn)},
        agent_id=agent.id,
    )
