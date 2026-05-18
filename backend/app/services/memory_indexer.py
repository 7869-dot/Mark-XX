"""Mines chat/task history into agent interest_tags, goals hints, and personality."""
import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models import (
    Agent,
    User,
    ChatHistory,
    Task,
    UserPersonality,
)
from app.models.agent import AgentMemoryType
from app.prompts.templates import MEMORY_MINE
from app.services.gemini import generate
from app.services.agent_service import add_memory
from app.services.profile_sync import sync_agent_profile
from app.core.logging import get_logger, log_event

logger = get_logger("axolot.memory_indexer")
KEYS = ["openness", "directness", "ambition", "sociability", "risk_tolerance"]


def _gather_history(db: Session, user: User) -> str:
    since = datetime.utcnow() - timedelta(days=30)
    chats = (
        db.query(ChatHistory)
        .filter(ChatHistory.user_id == user.id, ChatHistory.created_at >= since)
        .order_by(ChatHistory.created_at.asc())
        .limit(120)
        .all()
    )
    tasks = (
        db.query(Task)
        .filter(Task.user_id == user.id, Task.created_at >= since)
        .order_by(Task.created_at.asc())
        .limit(40)
        .all()
    )
    lines = [f"[{c.role}] {c.content}" for c in chats]
    lines += [f"[task] {t.title}: {t.description}" for t in tasks]
    return "\n".join(lines) or "No recent activity."


def derive_personality_from_history(history: str, mined: dict) -> dict:
    """Map mined insights + simple heuristics onto the 5-dim vector (0..1)."""
    notes = mined.get("personality_notes", {}) or {}
    style = (notes.get("communication_style", "") or "").lower()
    lines = [l for l in history.splitlines() if l.strip()]
    user_lines = [l for l in lines if l.startswith("[user]")]
    avg_len = (
        sum(len(l) for l in user_lines) / len(user_lines) if user_lines else 60
    )
    n_questions = sum(1 for l in user_lines if "?" in l)

    return {
        # many questions -> more exploratory
        "openness": min(1.0, 0.45 + (n_questions / max(len(user_lines), 1)) * 0.6),
        # short instructions / "direct" style -> higher directness
        "directness": 0.75 if ("direct" in style or avg_len < 80) else 0.45,
        # goals/deadlines mentioned -> ambition
        "ambition": min(1.0, 0.5 + 0.1 * len(mined.get("inferred_goals", []) or [])),
        # asks about others/collaborators -> sociability
        "sociability": 0.7 if "collab" in history.lower() else 0.45,
        # bold task actions -> risk tolerance
        "risk_tolerance": 0.65 if len(mined.get("notable_projects", []) or []) else 0.45,
    }


def mine_user(db: Session, agent: Agent) -> None:
    user: User = agent.user
    if not user:
        return
    history = _gather_history(db, user)
    raw = generate(MEMORY_MINE.format(conversation_history=history), response_format="memory_mine")
    try:
        mined = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        return

    # 1) Update interest tags on the user_personalities source, then sync to agent.
    tags = [str(t) for t in (mined.get("interest_tags") or [])][:15]
    personality = (
        db.query(UserPersonality).filter(UserPersonality.user_id == user.id).first()
    )
    if not personality:
        personality = UserPersonality(user_id=user.id, interests=[])
        db.add(personality)
        db.flush()
    if tags:
        personality.interests = tags
    pn = mined.get("personality_notes", {}) or {}
    personality.communication_style = pn.get("communication_style", personality.communication_style or "")
    personality.notes = json.dumps(mined.get("notable_projects", []))

    # 2) Soft-blend the derived personality vector into the agent.
    derived = derive_personality_from_history(history, mined)
    current = agent.personality_vector or {}
    agent.personality_vector = {
        k: round(current.get(k, 0.5) * 0.6 + float(derived.get(k, 0.5)) * 0.4, 3)
        for k in KEYS
    }
    db.commit()

    # 3) Re-sync interest_tags/goals onto the agent from the now-updated sources.
    sync_agent_profile(db, agent)

    # 4) Store the full mined output as a learned_preference memory.
    add_memory(
        db, agent, AgentMemoryType.learned_preference,
        f"[mined] {json.dumps(mined)[:1200]}",
        importance=0.65,
    )
    log_event(logger, "memory_mined", agent_id=agent.id, tags=len(tags))


def run_memory_mining(db: Session) -> int:
    count = 0
    for agent in db.query(Agent).all():
        try:
            mine_user(db, agent)
            count += 1
        except Exception as exc:  # noqa: BLE001
            log_event(logger, "memory_mine_failed", agent_id=agent.id, error=str(exc))
    return count
