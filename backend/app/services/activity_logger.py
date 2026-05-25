"""Single chokepoint for writing to agent_activity_log.

Every "the agent did X" should pass through here so the live activity feed
on the dashboard stays in sync with reality. Cheap inserts — no LLM, no
external calls. Safe to call from inside other DB transactions.
"""
from datetime import datetime, timedelta
from typing import Any

from sqlalchemy.orm import Session

from app.core.logging import get_logger, log_event
from app.models import AgentActivityLog, ActivityType

logger = get_logger("axolot.activity")


def log_activity(
    db: Session,
    agent_id: str,
    action_type: ActivityType,
    description: str,
    metadata: dict[str, Any] | None = None,
    commit: bool = True,
) -> AgentActivityLog | None:
    """Insert an activity row. Never raises — failures are observed only."""
    if not agent_id or not description:
        return None
    try:
        row = AgentActivityLog(
            agent_id=agent_id,
            action_type=action_type,
            description=description[:280],  # tight cap — these are headlines
            activity_metadata=metadata or {},
        )
        db.add(row)
        if commit:
            db.commit()
            db.refresh(row)
        return row
    except Exception as exc:  # noqa: BLE001
        # The activity log is a "nice to have" — never let it fail the caller.
        log_event(logger, "activity_log_failed", agent_id=agent_id, error=str(exc))
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return None


def recent_activity(db: Session, agent_id: str, limit: int = 30) -> list[dict]:
    rows = (
        db.query(AgentActivityLog)
        .filter(AgentActivityLog.agent_id == agent_id)
        .order_by(AgentActivityLog.created_at.desc())
        .limit(limit)
        .all()
    )
    return [
        {
            "id": r.id,
            "action_type": r.action_type.value,
            "description": r.description,
            "metadata": r.activity_metadata or {},
            "created_at": r.created_at.isoformat(),
        }
        for r in rows
    ]


def trim_old_activity(db: Session, retain_days: int = 30) -> int:
    """Housekeeping — keep the activity table bounded. Called by a scheduler job."""
    cutoff = datetime.utcnow() - timedelta(days=retain_days)
    deleted = (
        db.query(AgentActivityLog)
        .filter(AgentActivityLog.created_at < cutoff)
        .delete(synchronize_session=False)
    )
    db.commit()
    return deleted
