"""Agent inbox — async A2A messages. The "agent email" surface.

Read endpoints return threads bucketed for the recipient. Send endpoint
creates a new outbound message. Both endpoints resolve the *active* agent
via the X-Agent-Id header (see services.active_agent) so multi-agent users
can choose which of their agents speaks.
"""
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.models import Agent, AgentAvailability, User
from app.api.envelope import envelope
from app.services.active_agent import resolve_active_agent
from app.services import a2a_async

router = APIRouter(prefix="/agent", tags=["a2a-inbox"])


def _require_agent(db: Session, request: Request, user: User) -> Agent:
    x_agent_id = request.headers.get("X-Agent-Id")
    agent = resolve_active_agent(db, user, x_agent_id)
    if not agent:
        raise HTTPException(status_code=400, detail="no_agent")
    return agent


@router.get("/messages")
def get_messages(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    agent = _require_agent(db, request, user)
    threads = a2a_async.list_threads_for_agent(db, agent.id)
    unread = sum(t["unread_count"] for t in threads)
    return envelope({
        "agent_id": agent.id,
        "agent_name": agent.name,
        "unread_count": unread,
        "thread_count": len(threads),
        "threads": threads,
    })


class SendMessageBody(BaseModel):
    recipient_agent_id: str = Field(..., min_length=1)
    content: str = Field(..., min_length=1, max_length=4000)
    thread_id: str | None = None


@router.post("/send-message")
def send_message(
    body: SendMessageBody,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    sender = _require_agent(db, request, user)
    recipient = (
        db.query(Agent).filter(Agent.id == body.recipient_agent_id).first()
    )
    if not recipient:
        raise HTTPException(status_code=404, detail="recipient_not_found")
    if recipient.user_id == sender.user_id:
        raise HTTPException(status_code=400, detail="cannot_message_self")
    msg = a2a_async.send_message(
        db, sender, recipient, body.content, thread_id=body.thread_id,
    )
    return envelope({
        "id": msg.id,
        "thread_id": msg.thread_id,
        "created_at": msg.created_at.isoformat(),
        "hold_until": msg.hold_until.isoformat() if msg.hold_until else None,
    })


@router.post("/messages/{thread_id}/mark-read")
def mark_read(
    thread_id: str,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    agent = _require_agent(db, request, user)
    n = a2a_async.mark_thread_read(db, agent.id, thread_id)
    return envelope({"marked_read": n})


class AvailabilityBody(BaseModel):
    availability: str = Field(..., pattern="^(always_on|business_hours|dnd)$")


@router.put("/availability")
def update_availability(
    body: AvailabilityBody,
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    agent = _require_agent(db, request, user)
    agent.availability = AgentAvailability(body.availability)
    db.commit()
    db.refresh(agent)
    return envelope({"availability": agent.availability.value})


@router.get("/availability")
def get_availability(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    agent = _require_agent(db, request, user)
    return envelope({
        "availability": (agent.availability or AgentAvailability.always_on).value,
    })


@router.get("/activity")
def get_activity(
    request: Request,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Live agent activity log — powers the dashboard 'What your agent did' feed."""
    from app.services.activity_logger import recent_activity
    agent = _require_agent(db, request, user)
    return envelope({
        "agent_id": agent.id,
        "items": recent_activity(db, agent.id, limit=50),
    })
