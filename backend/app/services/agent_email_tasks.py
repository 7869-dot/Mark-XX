"""Agent-facing email task handlers. Persist task RESULTS only — never email bodies."""
import json
from datetime import datetime
from sqlalchemy.orm import Session

from app.models import Agent, Task, WatchedThread
from app.models.task import TaskType, TaskStatus, TaskTrigger
from app.services import gmail_service
from app.services.gemini import generate
from app.core.logging import get_logger, log_event

logger = get_logger("axolot.agent_email")


def _agent(db: Session, agent_id: str) -> Agent | None:
    return db.query(Agent).filter(Agent.id == agent_id).first()


def _new_task(db, agent, title, description, task_type, result=None,
              status=TaskStatus.completed, requires_human=False) -> Task:
    t = Task(
        agent_id=agent.id, user_id=agent.user_id, title=title,
        description=description, task_type=task_type, status=status,
        priority=3, requires_human_approval=requires_human,
        triggered_by=TaskTrigger.agent_self, result=result,
        completed_at=datetime.utcnow() if status == TaskStatus.completed else None,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def summarize_inbox(db: Session, agent_id: str) -> dict:
    agent = _agent(db, agent_id)
    if not agent:
        return {"error": "agent_not_found"}
    emails = gmail_service.list_emails(db, agent.user_id, max_results=20, unread_only=True)
    compact = [
        {"id": e["id"], "subject": e["subject"], "from": e["sender_email"],
         "snippet": e["snippet"]}
        for e in emails
    ]
    prompt = (
        f"Summarize these emails for {agent.user.name}. Group by: urgent (needs "
        f"reply today), important (needs reply this week), informational (no action). "
        f"For each urgent/important email suggest a one-line reply. Return JSON.\n\n"
        f"{json.dumps(compact)}"
    )
    raw = generate(prompt, response_format="inbox_summary")
    try:
        summary = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        summary = {"raw": raw}
    t = _new_task(
        db, agent, "Inbox summary",
        f"Summarized {len(emails)} unread emails", TaskType.analysis,
        result={"summary": "Inbox triaged", "result": summary},
    )
    log_event(logger, "summarize_inbox", agent_id=agent.id, count=len(emails), task=t.id)
    return {"task_id": t.id, "summary": summary}


def draft_reply(db: Session, agent_id: str, message_id: str, instruction: str) -> dict:
    agent = _agent(db, agent_id)
    if not agent:
        return {"error": "agent_not_found"}
    email = gmail_service.get_email(db, agent.user_id, message_id)
    pv = agent.personality_vector or {}
    prompt = (
        f"You are {agent.name}, writing on behalf of {agent.user.name}. "
        f"Personality: {pv}\n\nOriginal email:\nFrom: {email['sender']}\n"
        f"Subject: {email['subject']}\n{email['body_plain'][:1500]}\n\n"
        f"Instruction from user: {instruction}\n\n"
        f"Write a reply. Match the user's style. Be concise. Do not start with "
        f"'I hope this email finds you well.' Return only the email body."
    )
    body = generate(prompt, response_format="email_reply")
    draft_id = gmail_service.draft_email(
        db, agent.user_id, to=email["sender_email"],
        subject="Re: " + email["subject"], body=body,
    )
    t = _new_task(
        db, agent, f"Draft reply: {email['subject'][:60]}",
        f"Drafted a reply to {email['sender_email']}", TaskType.outreach,
        result={"summary": "Reply drafted — awaiting your review",
                "result": body, "draft_id": draft_id, "message_id": message_id},
        status=TaskStatus.awaiting_human, requires_human=True,
    )
    return {"task_id": t.id, "draft_id": draft_id, "draft_body": body}


def schedule_meeting(db: Session, agent_id: str, with_email: str, purpose: str,
                     duration_minutes: int = 30, preferred_days=None) -> dict:
    from app.services import calendar_service

    agent = _agent(db, agent_id)
    if not agent:
        return {"error": "agent_not_found"}
    slots = []
    base = datetime.utcnow()
    for d in range(1, 8):
        day = base + __import__("datetime").timedelta(days=d)
        if day.weekday() >= 5:
            continue
        free = calendar_service.find_free_slots(
            db, agent.user_id, day.strftime("%Y-%m-%d"), duration_minutes
        )
        slots.extend(free[:2])
        if len(slots) >= 3:
            break
    top = slots[:3]
    pv = agent.personality_vector or {}
    prompt = (
        f"Write a brief email to {with_email} proposing these 3 time slots for a "
        f"{duration_minutes}-minute call about {purpose}. Slots: {top}. "
        f"Tone tuned to directness={pv.get('directness',0.5)}. Return only the body."
    )
    body = generate(prompt, response_format="schedule_email")
    draft_id = gmail_service.draft_email(
        db, agent.user_id, to=with_email,
        subject=f"Quick call about {purpose}?", body=body,
    )
    t = _new_task(
        db, agent, f"Schedule: {purpose[:50]}",
        f"Drafted scheduling email to {with_email}", TaskType.scheduling,
        result={"summary": "Scheduling email drafted",
                "result": body, "draft_id": draft_id, "proposed_slots": top},
        status=TaskStatus.awaiting_human, requires_human=True,
    )
    return {"task_id": t.id, "draft_id": draft_id, "proposed_slots": top, "draft_body": body}


def monitor_thread(db: Session, agent_id: str, thread_id: str,
                   check_interval_hours: int = 4) -> dict:
    agent = _agent(db, agent_id)
    if not agent:
        return {"error": "agent_not_found"}
    existing = db.query(WatchedThread).filter(
        WatchedThread.agent_id == agent.id,
        WatchedThread.thread_id == thread_id,
        WatchedThread.is_active == True,  # noqa: E712
    ).first()
    if existing:
        return {"watched": True, "id": existing.id, "already": True}
    thread = gmail_service.get_thread(db, agent.user_id, thread_id)
    last_id = gmail_service.latest_message_id(db, agent.user_id, thread_id)
    wt = WatchedThread(
        agent_id=agent.id, user_id=agent.user_id, thread_id=thread_id,
        subject=thread.get("subject", ""), last_message_id=last_id,
        check_interval_hours=check_interval_hours,
    )
    db.add(wt)
    db.commit()
    db.refresh(wt)
    log_event(logger, "thread_watched", agent_id=agent.id, thread_id=thread_id)
    return {"watched": True, "id": wt.id}


def weekly_email_digest(db: Session, agent_id: str) -> dict:
    agent = _agent(db, agent_id)
    if not agent:
        return {"error": "agent_not_found"}
    recent = gmail_service.search_emails(db, agent.user_id, "newer_than:7d", max_results=50)
    prompt = (
        f"Write a weekly email digest for {agent.user.name}: volume, top senders, "
        f"threads needing follow-up. Data: {json.dumps(recent[:30])}"
    )
    digest = generate(prompt, response_format="email_digest")
    t = _new_task(
        db, agent, "Weekly email digest",
        "Summary of the past 7 days of email", TaskType.analysis,
        result={"summary": digest, "result": digest},
    )
    return {"task_id": t.id, "digest": digest}
