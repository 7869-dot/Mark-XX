"""Builds full context for a Gemini call from the 4-layer memory pipeline.

Layers:
  1. ChatHistory          — last CHAT_WINDOW user/agent turns
  2. ConversationSummary  — rolling Gemini-compressed summary of older chat
  3. UserPersonality      — long-term "what I know about you" snapshot
  4. AgentMemory          — agent's own memories (interactions, posts, milestones)

build_agent_context(...) returns the dict consumed by the chat / task prompt
templates (CHAT_CONVERSATION, TASK_EXECUTION, GOAL_TASKS).

build_voice_prompt(...) wraps that same context into a stand-alone prompt for
the gemini.generate_for_agent helper — used by proactive jobs (briefings,
alerts, autonomous posts) so an agent's voice is consistent everywhere.
"""
from sqlalchemy.orm import Session
from app.core.logging import get_logger, log_event
from app.models import Agent, AgentMemory, ChatHistory, ConversationSummary, UserPersonality, User

logger = get_logger("axolot.context_builder")

# Per Sprint 3 spec: last N=20 turns always injected into Gemini context.
CHAT_WINDOW = 20

# Communication context (Gmail/Calendar) is only relevant for these task types.
_COMM_TASK_TYPES = {"outreach", "scheduling", "analysis"}


def get_communication_context(db: Session, user: User) -> str:
    """Upcoming schedule + connection state, for outreach/scheduling/analysis tasks."""
    try:
        from app.services.calendar_service import get_upcoming_summary

        upcoming = (
            get_upcoming_summary(db, user.id, days=2)
            if getattr(user, "calendar_connected", False)
            else "Calendar not connected."
        )
    except Exception:  # noqa: BLE001
        upcoming = "Calendar unavailable."
    return (
        "Communication context:\n"
        f"Upcoming schedule:\n{upcoming}\n"
        f"Gmail connected: {bool(getattr(user, 'gmail_connected', False))}"
    )


def build_agent_context(db: Session, agent: Agent, task_type: str | None = None) -> dict:
    user: User = agent.user

    personality = db.query(UserPersonality).filter(UserPersonality.user_id == user.id).first()
    personality_summary = ""
    if personality:
        personality_summary = (
            f"Communication style: {personality.communication_style or 'unspecified'}. "
            f"Interests: {', '.join(personality.interests or [])}. "
            f"Notes: {personality.notes or 'none'}."
        )

    # Structured speech-mirror block — null-safe, generates a neutral block
    # when the profile hasn't been populated yet.
    from app.services.speech_profile import speech_mirror_block
    speech_mirror = speech_mirror_block(personality)

    recent_chats = (
        db.query(ChatHistory)
        .filter(ChatHistory.user_id == user.id)
        .order_by(ChatHistory.created_at.desc())
        .limit(CHAT_WINDOW)
        .all()
    )
    # Gemini requires strict user/model alternation in chat history. If two
    # consecutive turns share a role (e.g. user retried mid-call and we logged
    # two `user` rows before any agent reply), collapse them or insert a
    # bridge so the role sequence stays alternating. The text-only prompt path
    # is more forgiving but the future tools path uses chat.send_message
    # directly — keeping this clean here makes that swap safe.
    ordered = list(reversed(recent_chats))
    collapsed: list[ChatHistory] = []
    for c in ordered:
        if collapsed and collapsed[-1].role == c.role:
            # Merge consecutive same-role turns into the latest content — losing
            # the older one is preferable to crashing Gemini on a role error.
            collapsed[-1] = c
        else:
            collapsed.append(c)
    chat_text = "\n".join(f"[{c.role}] {c.content}" for c in collapsed) or "No recent conversation."

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

    world = ""
    if task_type in _COMM_TASK_TYPES:
        world = get_communication_context(db, user)

    goals = user.goals or []
    goals_text = "\n".join(f"- {g}" for g in goals) or "No goals set yet."

    pv = agent.personality_vector or {}

    ctx = {
        "agent_name": agent.name,
        "agent_bio": agent.bio or "",
        "agent_system_prompt": agent.system_prompt or "",
        "user_name": user.name or "User",
        "openness": pv.get("openness", 0.5),
        "directness": pv.get("directness", 0.5),
        "ambition": pv.get("ambition", 0.5),
        "sociability": pv.get("sociability", 0.5),
        "risk_tolerance": pv.get("risk_tolerance", 0.5),
        "goals_list": goals_text,
        "personality_summary": personality_summary or summary_text,
        "speech_mirror": speech_mirror,
        "conversation_summary": summary_text or "No prior summaries.",
        "agent_memories": memory_text,
        "world_context": world,
        "recent_chats": chat_text,
    }
    # Lightweight observability — char count is a reliable proxy for token
    # cost and we don't want to pull tiktoken in.
    total_chars = sum(len(str(v)) for v in ctx.values())
    log_event(
        logger, "context_built",
        agent_id=agent.id, user_id=user.id, chars=total_chars,
        approx_tokens=total_chars // 4,
    )
    return ctx


def build_voice_prompt(db: Session, agent: Agent, instruction: str) -> str:
    """Single prompt assembled from the full pipeline for agent-as-itself calls.

    Used by gemini.generate_for_agent — the canonical path for autonomous
    posts, morning briefings, inbox alerts and any other surface where the
    agent must sound like itself. Mirrors the structure of CHAT_CONVERSATION
    but ends with a free-form instruction instead of a user message.
    """
    ctx = build_agent_context(db, agent)
    voice_lines = []
    if ctx["agent_system_prompt"]:
        # A marketplace template can fully override the default voice.
        voice_lines.append(ctx["agent_system_prompt"])
    voice_lines.append(
        f"You are {ctx['agent_name']}, the persistent digital agent of {ctx['user_name']}."
    )
    if ctx["agent_bio"]:
        voice_lines.append(f"Your bio: {ctx['agent_bio']}")
    voice_lines.append(
        "Your personality vector — "
        f"openness {ctx['openness']}, directness {ctx['directness']}, "
        f"ambition {ctx['ambition']}, sociability {ctx['sociability']}, "
        f"risk_tolerance {ctx['risk_tolerance']}."
    )
    # Social persona (Sprint 3) — the single place every agent-as-itself surface
    # picks up its distinct voice. Only emitted when the agent has set persona.
    persona_bits = []
    if agent.voice_tone:
        persona_bits.append(f"tone: {agent.voice_tone}")
    if agent.posting_style:
        persona_bits.append(f"posting style: {agent.posting_style}")
    if agent.response_style:
        persona_bits.append(f"how you engage others: {agent.response_style}")
    core = agent.core_interests or agent.interest_tags or []
    if core:
        persona_bits.append(f"core interests: {', '.join(map(str, core[:8]))}")
    if persona_bits:
        voice_lines.append(
            "Your social persona — " + "; ".join(persona_bits)
            + ". Stay unmistakably true to this voice in everything you write."
        )
    return (
        "\n".join(voice_lines)
        + "\n\nWhat you know about your user:\n"
        + ctx["personality_summary"]
        + "\n\nConversation summary so far:\n"
        + ctx["conversation_summary"]
        + "\n\nYour recent memories:\n"
        + ctx["agent_memories"]
        + "\n\nWorld context:\n"
        + ctx["world_context"]
        + "\n\nRecent conversation with your user:\n"
        + ctx["recent_chats"]
        + "\n\nInstruction:\n"
        + instruction
        + "\n\nReply only with the requested content. No preamble."
    )
