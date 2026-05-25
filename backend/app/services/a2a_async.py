"""Async agent-to-agent messaging — the agent equivalent of email.

Agents send messages to other agents. The recipient's agent processes them
on its next pass (poll + 5-min scheduler sweeper) and may auto-reply using
its owner's personality. Messages held while owner is in DND.
"""
from datetime import datetime, timedelta

from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.core.logging import get_logger, log_event
from app.models import (
    ActivityType,
    Agent,
    AgentAvailability,
    AgentMessage,
)
from app.services.activity_logger import log_activity
from app.services.context_builder import build_voice_prompt
from app.services.gemini import generate

logger = get_logger("axolot.a2a_async")

# Strong, explicit "no-filter" prompt — A2A is agent talking to agent, not
# agent placating a human. Repeated from spec because the directness is the
# whole point of the surface.
_NO_FILTER_SYSTEM = (
    "You are communicating with another AI agent representing a real human. "
    "Speak naturally, as your user would speak. No corporate tone, no "
    "disclaimers, no over-politeness. Be direct, efficient, and human. "
    "Two or three sentences. No \"I hope this finds you well\" type filler."
)


def _availability(agent: Agent) -> AgentAvailability:
    return agent.availability or AgentAvailability.always_on


def _is_within_business_hours(now: datetime | None = None) -> bool:
    # 9am–6pm UTC as a conservative default. Per-user TZ would be the next
    # step but is out of scope for the first cut — the spec only requires
    # the gate to exist.
    now = now or datetime.utcnow()
    return 9 <= now.hour < 18


def _delivery_hold_until(recipient: Agent) -> datetime | None:
    avail = _availability(recipient)
    if avail == AgentAvailability.always_on:
        return None
    if avail == AgentAvailability.business_hours:
        if _is_within_business_hours():
            return None
        # Hold until next 9am UTC.
        now = datetime.utcnow()
        target = now.replace(hour=9, minute=0, second=0, microsecond=0)
        if target <= now:
            target = target + timedelta(days=1)
        return target
    # DND — park 24h; user can manually flush by toggling availability.
    return datetime.utcnow() + timedelta(days=1)


def send_message(
    db: Session,
    sender: Agent,
    recipient: Agent,
    content: str,
    thread_id: str | None = None,
) -> AgentMessage:
    """Persist a new A2A message. Always succeeds (no live network)."""
    content = (content or "").strip()
    if not content:
        raise ValueError("content must not be empty")
    msg = AgentMessage(
        sender_agent_id=sender.id,
        recipient_agent_id=recipient.id,
        thread_id=thread_id or "",  # filled in below once we have an id
        content=content[:4000],
        hold_until=_delivery_hold_until(recipient),
        delivered=True,
        processed=False,
        read=False,
    )
    db.add(msg)
    db.commit()
    db.refresh(msg)
    if not msg.thread_id:
        msg.thread_id = msg.id
        db.commit()

    log_activity(
        db, sender.id, ActivityType.a2a_sent,
        f"Sent a message to {recipient.name}.",
        metadata={"message_id": msg.id, "recipient_agent_id": recipient.id},
    )
    log_activity(
        db, recipient.id, ActivityType.a2a_received,
        f"Received a message from {sender.name}.",
        metadata={"message_id": msg.id, "sender_agent_id": sender.id},
    )
    log_event(
        logger, "a2a_sent",
        sender_agent_id=sender.id, recipient_agent_id=recipient.id,
        hold_until=msg.hold_until.isoformat() if msg.hold_until else None,
    )
    return msg


def list_threads_for_agent(db: Session, agent_id: str) -> list[dict]:
    """Group inbound + outbound messages by thread_id, newest thread first."""
    rows = (
        db.query(AgentMessage)
        .filter(or_(
            AgentMessage.recipient_agent_id == agent_id,
            AgentMessage.sender_agent_id == agent_id,
        ))
        .order_by(AgentMessage.created_at.desc())
        .all()
    )
    by_thread: dict[str, list[AgentMessage]] = {}
    for m in rows:
        by_thread.setdefault(m.thread_id, []).append(m)

    threads: list[dict] = []
    for tid, msgs in by_thread.items():
        msgs.sort(key=lambda m: m.created_at)
        latest = msgs[-1]
        other_id = (
            latest.recipient_agent_id
            if latest.sender_agent_id == agent_id
            else latest.sender_agent_id
        )
        other = db.query(Agent).filter(Agent.id == other_id).first()
        unread = sum(
            1 for m in msgs
            if m.recipient_agent_id == agent_id and not m.read
        )
        threads.append({
            "thread_id": tid,
            "other_agent": {
                "id": other.id if other else other_id,
                "name": other.name if other else "Unknown agent",
                "avatar_seed": other.avatar_seed if other else other_id,
            },
            "preview": latest.content[:120],
            "unread_count": unread,
            "message_count": len(msgs),
            "last_at": latest.created_at.isoformat(),
            "messages": [
                {
                    "id": m.id,
                    "from_me": m.sender_agent_id == agent_id,
                    "content": m.content,
                    "created_at": m.created_at.isoformat(),
                    "read": m.read,
                    "processed": m.processed,
                }
                for m in msgs
            ],
        })
    threads.sort(key=lambda t: t["last_at"], reverse=True)
    return threads


def mark_thread_read(db: Session, agent_id: str, thread_id: str) -> int:
    n = (
        db.query(AgentMessage)
        .filter(
            AgentMessage.thread_id == thread_id,
            AgentMessage.recipient_agent_id == agent_id,
            AgentMessage.read == False,  # noqa: E712
        )
        .update({"read": True}, synchronize_session=False)
    )
    db.commit()
    return n


def process_unread_for_agent(db: Session, agent: Agent, max_replies: int = 3) -> int:
    """Generate auto-replies for unread A2A messages.

    Only processes messages past their hold_until. DND agents skip entirely.
    Returns the number of replies generated.
    """
    avail = _availability(agent)
    if avail == AgentAvailability.dnd:
        return 0

    now = datetime.utcnow()
    unread = (
        db.query(AgentMessage)
        .filter(
            AgentMessage.recipient_agent_id == agent.id,
            AgentMessage.processed == False,  # noqa: E712
            or_(AgentMessage.hold_until == None, AgentMessage.hold_until <= now),  # noqa: E711
        )
        .order_by(AgentMessage.created_at)
        .limit(max_replies)
        .all()
    )
    replies = 0
    for incoming in unread:
        sender_agent = (
            db.query(Agent)
            .filter(Agent.id == incoming.sender_agent_id)
            .first()
        )
        if not sender_agent:
            incoming.processed = True
            incoming.processed_at = datetime.utcnow()
            continue
        instruction = (
            _NO_FILTER_SYSTEM
            + f"\n\nThe other agent ({sender_agent.name}) just wrote:\n"
            + f"\"{incoming.content}\"\n\n"
            + "Reply in 2-3 sentences. Be specific. No filler."
        )
        prompt = build_voice_prompt(db, agent, instruction)
        reply_text = (generate(prompt, response_format="response") or "").strip()
        if not reply_text:
            reply_text = "Got it — let me check with my user and come back to you."
        send_message(db, agent, sender_agent, reply_text, thread_id=incoming.thread_id)

        incoming.processed = True
        incoming.processed_at = datetime.utcnow()
        log_activity(
            db, agent.id, ActivityType.a2a_replied,
            f"Replied to {sender_agent.name}.",
            metadata={"thread_id": incoming.thread_id},
        )
        replies += 1
    db.commit()
    return replies


def process_all_unread(db: Session) -> int:
    """Scheduler entry — process inbox for every agent. Returns total replies."""
    total = 0
    for a in db.query(Agent).all():
        try:
            total += process_unread_for_agent(db, a)
        except Exception as exc:  # noqa: BLE001
            log_event(logger, "a2a_process_failed", agent_id=a.id, error=str(exc))
    return total
