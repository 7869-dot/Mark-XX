"""Builds full context for a Gemini call from the 6-layer memory pipeline."""
from sqlalchemy.orm import Session
from app.models import Agent, AgentMemory, ChatHistory, ConversationSummary, UserPersonality, User
from app.services.world_context import build_world_context


def build_agent_context(db: Session, agent: Agent) -> dict:
    user: User = agent.user

    personality = db.query(UserPersonality).filter(UserPersonality.user_id == user.id).first()
    personality_summary = ""
    if personality:
        personality_summary = (
            f"Communication style: {personality.communication_style or 'unspecified'}. "
            f"Interests: {', '.join(personality.interests or [])}. "
            f"Notes: {personality.notes or 'none'}."
        )

    recent_chats = (
        db.query(ChatHistory)
        .filter(ChatHistory.user_id == user.id)
        .order_by(ChatHistory.created_at.desc())
        .limit(8)
        .all()
    )
    chat_text = "\n".join(f"[{c.role}] {c.content}" for c in reversed(recent_chats)) or "No recent conversation."

    summaries = (
        db.query(ConversationSummary)
        .filter(ConversationSummary.user_id == user.id)
        .order_by(ConversationSummary.created_at.desc())
        .limit(3)
        .all()
    )
    summary_text = "\n".join(s.summary for s in summaries) or "No prior summaries."

    memories = (
        db.query(AgentMemory)
        .filter(AgentMemory.agent_id == agent.id)
        .order_by(AgentMemory.importance_score.desc(), AgentMemory.created_at.desc())
        .limit(6)
        .all()
    )
    memory_text = "\n".join(f"- {m.content}" for m in memories) or "No notable memories yet."

    world = build_world_context(db)

    goals = user.goals or []
    goals_text = "\n".join(f"- {g}" for g in goals) or "No goals set yet."

    pv = agent.personality_vector or {}

    return {
        "agent_name": agent.name,
        "user_name": user.name,
        "openness": pv.get("openness", 0.5),
        "directness": pv.get("directness", 0.5),
        "ambition": pv.get("ambition", 0.5),
        "sociability": pv.get("sociability", 0.5),
        "risk_tolerance": pv.get("risk_tolerance", 0.5),
        "goals_list": goals_text,
        "personality_summary": personality_summary or summary_text,
        "agent_memories": memory_text,
        "world_context": world,
        "recent_chats": chat_text,
    }
