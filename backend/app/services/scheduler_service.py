"""Per-agent scheduler control: enable/disable autonomous behaviors.

The APScheduler jobs in scheduler/proactive_jobs.py fan out across every agent
and consult `scheduled_jobs` to decide whether to act for each one. This module
is the small surface that creates the default rows for a new agent and toggles
them from the API.
"""
from __future__ import annotations

from datetime import datetime
from typing import Iterable

from sqlalchemy.orm import Session

from app.models import Agent, ScheduledJob
from app.models.scheduler import (
    ALL_JOB_TYPES,
    JOB_AUTO_POST,
    JOB_INBOX_MONITOR,
    JOB_MORNING_BRIEFING,
)

# Defaults chosen to feel alive out of the box: briefing + inbox alerts on
# (still gated by Gmail/Calendar connection), auto_post off until the user
# opts in via the schedule endpoint or a marketplace template.
DEFAULT_ENABLED = {
    JOB_MORNING_BRIEFING: True,
    JOB_INBOX_MONITOR: True,
    JOB_AUTO_POST: False,
}
DEFAULT_CRON = {
    JOB_MORNING_BRIEFING: "0 8 * * *",       # 8:00am daily
    JOB_INBOX_MONITOR: "*/30 * * * *",       # every 30 minutes
    JOB_AUTO_POST: "off",                    # set to 'daily' or 'weekly' by user
}


def ensure_default_jobs(db: Session, agent: Agent) -> None:
    """Create the three default ScheduledJob rows for a freshly-minted agent.

    Idempotent — does nothing if the rows already exist.
    """
    existing = {
        r.job_type
        for r in db.query(ScheduledJob.job_type)
        .filter(ScheduledJob.agent_id == agent.id)
        .all()
    }
    for job_type in ALL_JOB_TYPES:
        if job_type in existing:
            continue
        db.add(
            ScheduledJob(
                agent_id=agent.id,
                job_type=job_type,
                enabled=DEFAULT_ENABLED[job_type],
                cron_expr=DEFAULT_CRON[job_type],
            )
        )
    db.commit()


def get_schedule(db: Session, agent_id: str) -> list[dict]:
    """Return the agent's full schedule as a list — backfills missing rows.

    Returning a list (not a dict) keeps the wire format stable as more job types
    are added.
    """
    rows = (
        db.query(ScheduledJob)
        .filter(ScheduledJob.agent_id == agent_id)
        .all()
    )
    have = {r.job_type for r in rows}
    if have != set(ALL_JOB_TYPES):
        # Self-heal: an agent created before this migration won't have rows yet.
        agent = db.query(Agent).filter(Agent.id == agent_id).first()
        if agent:
            ensure_default_jobs(db, agent)
        rows = (
            db.query(ScheduledJob)
            .filter(ScheduledJob.agent_id == agent_id)
            .all()
        )
    return [
        {
            "job_type": r.job_type,
            "enabled": bool(r.enabled),
            "cron_expr": r.cron_expr,
            "last_run": r.last_run.isoformat() if r.last_run else None,
            "next_run": r.next_run.isoformat() if r.next_run else None,
        }
        for r in sorted(rows, key=lambda r: r.job_type)
    ]


def set_schedule(
    db: Session,
    agent: Agent,
    morning_briefing: bool | None = None,
    inbox_monitor: bool | None = None,
    auto_post: str | None = None,
) -> list[dict]:
    """Toggle one or more behaviors. `auto_post` is the enum string off|daily|weekly.

    Only non-None fields are written, so partial updates work.
    """
    ensure_default_jobs(db, agent)

    def _row(job_type: str) -> ScheduledJob:
        return (
            db.query(ScheduledJob)
            .filter(
                ScheduledJob.agent_id == agent.id,
                ScheduledJob.job_type == job_type,
            )
            .first()
        )

    if morning_briefing is not None:
        _row(JOB_MORNING_BRIEFING).enabled = bool(morning_briefing)
    if inbox_monitor is not None:
        _row(JOB_INBOX_MONITOR).enabled = bool(inbox_monitor)
    if auto_post is not None:
        if auto_post not in {"off", "daily", "weekly"}:
            raise ValueError("auto_post must be off|daily|weekly")
        agent.auto_post_schedule = auto_post
        row = _row(JOB_AUTO_POST)
        row.enabled = auto_post != "off"
        row.cron_expr = auto_post

    db.commit()
    return get_schedule(db, agent.id)


def enabled_agents_for(db: Session, job_type: str) -> list[Agent]:
    """Agents whose scheduled_jobs row for this behavior is enabled."""
    return (
        db.query(Agent)
        .join(ScheduledJob, ScheduledJob.agent_id == Agent.id)
        .filter(
            ScheduledJob.job_type == job_type,
            ScheduledJob.enabled == True,  # noqa: E712
        )
        .all()
    )


def mark_ran(db: Session, agent_id: str, job_type: str) -> None:
    row = (
        db.query(ScheduledJob)
        .filter(
            ScheduledJob.agent_id == agent_id,
            ScheduledJob.job_type == job_type,
        )
        .first()
    )
    if row:
        row.last_run = datetime.utcnow()
        db.commit()


def auto_post_should_run_today(schedule: str, today: datetime | None = None) -> bool:
    """True if an auto_post agent should post today, given its schedule string."""
    if schedule == "daily":
        return True
    if schedule == "weekly":
        # Weekly = Monday, matching the existing weekly_email_digest convention.
        d = today or datetime.utcnow()
        return d.weekday() == 0
    return False
