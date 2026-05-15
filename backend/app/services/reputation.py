"""Event-sourced reputation.

reputation_score is NEVER mutated directly. It is recomputed as
    clamp(50 + sum(all deltas), 0, 100)
from the immutable reputation_events log. This makes it auditable and reversible.
"""
from sqlalchemy import func
from sqlalchemy.orm import Session

from app.models import Agent
from app.models.system import ReputationEvent
from app.core.logging import get_logger, log_event

logger = get_logger("axolot.reputation")
BASELINE = 50.0

# Canonical deltas per event type.
DELTAS = {
    "task_completed": 0.5,
    "task_approved": 1.0,
    "task_rejected": -1.5,
    "interaction_accepted": 1.2,
    "interaction_declined": -0.8,
    "inactive_decay": None,  # computed dynamically toward baseline
}


def _clamp(v: float) -> float:
    return max(0.0, min(100.0, v))


def record_event(
    db: Session,
    agent: Agent,
    event_type: str,
    reason: str = "",
    delta: float | None = None,
) -> float:
    """Append a reputation event and recompute the cached score."""
    if delta is None:
        delta = DELTAS.get(event_type, 0.0) or 0.0
    evt = ReputationEvent(
        agent_id=agent.id, event_type=event_type, delta=delta, reason=reason
    )
    db.add(evt)
    db.flush()
    new_score = recompute(db, agent)
    db.commit()
    log_event(
        logger,
        "reputation_event",
        agent_id=agent.id,
        event_type=event_type,
        delta=delta,
        new_score=new_score,
    )
    return new_score


def recompute(db: Session, agent: Agent) -> float:
    total = (
        db.query(func.coalesce(func.sum(ReputationEvent.delta), 0.0))
        .filter(ReputationEvent.agent_id == agent.id)
        .scalar()
        or 0.0
    )
    score = _clamp(BASELINE + float(total))
    agent.reputation_score = score  # cached projection of the event log
    return score


def decay_toward_baseline(db: Session, agent: Agent, rate: float = 0.05) -> float:
    """Record a decay event nudging the score toward baseline (for inactivity)."""
    current = agent.reputation_score if agent.reputation_score is not None else BASELINE
    delta = (BASELINE - current) * rate
    return record_event(db, agent, "inactive_decay", reason="inactive", delta=delta)
