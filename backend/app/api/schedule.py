"""Per-agent schedule endpoints — toggle the proactive behaviors.

Only the owning user can toggle their own agent's schedule. The actual
APScheduler jobs are registered once at startup and fan out per agent — these
endpoints just flip the rows in `scheduled_jobs`.
"""
from typing import Literal

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from app.api.envelope import envelope
from app.core.db import get_db
from app.core.security import get_current_user
from app.models import Agent, User
from app.services.scheduler_service import get_schedule, set_schedule

router = APIRouter(tags=["schedule"])


class ScheduleUpdate(BaseModel):
    morning_briefing: bool | None = None
    inbox_monitor: bool | None = None
    auto_post: Literal["off", "daily", "weekly"] | None = None
    ghost_post: bool | None = None


def _owned_agent(db: Session, agent_id: str, user: User) -> Agent:
    agent = db.query(Agent).filter(Agent.id == agent_id).first()
    if not agent:
        raise HTTPException(status_code=404, detail="Agent not found")
    if agent.user_id != user.id:
        raise HTTPException(
            status_code=403, detail="You can only manage your own agent's schedule"
        )
    return agent


@router.get("/agents/{agent_id}/schedule")
def get_agent_schedule(
    agent_id: str,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    agent = _owned_agent(db, agent_id, user)
    return envelope(
        {"jobs": get_schedule(db, agent.id), "auto_post_schedule": agent.auto_post_schedule},
        agent_id=agent.id,
    )


@router.put("/agents/{agent_id}/schedule")
def update_agent_schedule(
    agent_id: str,
    payload: ScheduleUpdate,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    agent = _owned_agent(db, agent_id, user)
    try:
        jobs = set_schedule(
            db, agent,
            morning_briefing=payload.morning_briefing,
            inbox_monitor=payload.inbox_monitor,
            auto_post=payload.auto_post,
            ghost_post=payload.ghost_post,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc))
    return envelope(
        {"jobs": jobs, "auto_post_schedule": agent.auto_post_schedule},
        agent_id=agent.id,
    )
