"""Sub-agent run logging — one AgentRunLog row per email/web run.

Powers GET /agents/status (last run time + one-line summary + status). The
agent_name is the internal role: email_agent | web_agent.
"""
from __future__ import annotations

from datetime import datetime

from sqlalchemy.orm import Session

from app.core.logging import get_logger, log_event
from app.models import AgentRunLog

logger = get_logger("axolot.agent_runs")

EMAIL_AGENT = "email_agent"
WEB_AGENT = "web_agent"
SUB_AGENTS = (EMAIL_AGENT, WEB_AGENT)


def log_run(db: Session, user_id: str, agent_name: str, summary: str, status: str = "ok") -> AgentRunLog:
    """Record a sub-agent run. Best-effort; commits its own row."""
    row = AgentRunLog(
        user_id=user_id,
        agent_name=agent_name,
        ran_at=datetime.utcnow(),
        report_summary=(summary or "")[:1000],
        status=status,
    )
    db.add(row)
    db.commit()
    db.refresh(row)
    log_event(logger, "agent_run_logged", user_id=user_id, agent=agent_name, status=status)
    return row


def last_runs(db: Session, user_id: str) -> dict[str, AgentRunLog | None]:
    """Most recent run row per sub-agent (None when an agent hasn't run yet)."""
    out: dict[str, AgentRunLog | None] = {name: None for name in SUB_AGENTS}
    for name in SUB_AGENTS:
        out[name] = (
            db.query(AgentRunLog)
            .filter(AgentRunLog.user_id == user_id, AgentRunLog.agent_name == name)
            .order_by(AgentRunLog.ran_at.desc())
            .first()
        )
    return out
