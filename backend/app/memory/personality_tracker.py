"""Counter-based UserPersonality refresh.

The Sprint 3 spec wants the long-term user-personality snapshot to be re-derived
"after every 5 conversations" — not just on the weekly cron. This module runs
as a BackgroundTask from /chat/message: every 5th user-authored message, we
re-mine the user's history into UserPersonality + the agent's interest_tags
via the existing memory_indexer.mine_user pipeline (so the cadence logic lives
in exactly one place).
"""
from __future__ import annotations

from app.core.db import SessionLocal
from app.core.logging import get_logger, log_event
from app.models import ChatHistory
from app.services.agent_service import get_primary_agent

logger = get_logger("axolot.personality_tracker")

# One user message ≈ one conversational turn from the human side. We trigger on
# every 5th turn, which matches the spec's "every 5 conversations".
REFRESH_EVERY = 5


def user_turn_count(db, user_id: str) -> int:
    return (
        db.query(ChatHistory)
        .filter(ChatHistory.user_id == user_id, ChatHistory.role == "user")
        .count()
    )


def refresh_personality_if_due(user_id: str) -> None:
    """Owns its own DB session — designed for BackgroundTasks (FastAPI closes
    the request session before background tasks run)."""
    db = SessionLocal()
    try:
        count = user_turn_count(db, user_id)
        if count == 0 or count % REFRESH_EVERY != 0:
            return
        agent = get_primary_agent(db, user_id)
        if not agent:
            return
        from app.services.memory_indexer import mine_user

        mine_user(db, agent)
        log_event(
            logger, "personality_refreshed",
            user_id=user_id, agent_id=agent.id, user_turns=count,
        )
    except Exception as exc:  # noqa: BLE001 — background work never raises
        log_event(logger, "personality_refresh_failed",
                  user_id=user_id, error=str(exc))
    finally:
        db.close()
