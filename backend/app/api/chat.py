"""Conversational chat between a user and their own agent.

Persists turns to ChatHistory (the existing memory pipeline owns summarization
and personality derivation downstream — this router only appends turns).
"""
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models import User, ChatHistory
from app.api.envelope import envelope
from app.prompts.templates import CHAT_CONVERSATION
from app.services.context_builder import build_agent_context
from app.services import gemini
from app.services.agent_service import create_agent_for_user
from app.memory.summarizer import summarize_user

router = APIRouter(prefix="/chat", tags=["chat"])


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
def message(body: dict, background_tasks: BackgroundTasks,
            db: Session = Depends(get_db),
            user: User = Depends(get_current_user)):
    text = (body.get("message") or "").strip()
    if not text:
        raise HTTPException(status_code=400, detail="message is required")

    if not user.agent:
        create_agent_for_user(db, user)
        db.refresh(user)
    agent = user.agent

    user_turn = ChatHistory(user_id=user.id, role="user", content=text)
    db.add(user_turn)
    db.commit()

    ctx = build_agent_context(db, agent)
    prompt = CHAT_CONVERSATION.format(user_message=text, **ctx)
    reply = (gemini.generate(prompt, response_format="text") or "").strip()
    if not reply:
        reply = "I'm here, but I couldn't form a response just now. Try again?"

    agent_turn = ChatHistory(user_id=user.id, role="agent", content=reply)
    db.add(agent_turn)
    db.commit()
    db.refresh(agent_turn)

    # Compress the conversation into ConversationSummary off the response path.
    background_tasks.add_task(summarize_user, user.id)

    return envelope(
        {"reply": _serialize(agent_turn), "echo": _serialize(user_turn)},
        agent_id=agent.id,
    )
