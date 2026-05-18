"""Agent-facing calendar task handlers. Persist results only."""
import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.models import Agent, Task
from app.models.task import TaskType, TaskStatus, TaskTrigger
from app.services import calendar_service, gmail_service
from app.services.gemini import generate
from app.core.logging import get_logger, log_event

logger = get_logger("axolot.agent_calendar")


def _agent(db, agent_id):
    return db.query(Agent).filter(Agent.id == agent_id).first()


def _task(db, agent, title, desc, ttype, result, status=TaskStatus.completed,
          requires_human=False):
    t = Task(
        agent_id=agent.id, user_id=agent.user_id, title=title, description=desc,
        task_type=ttype, status=status, priority=3,
        requires_human_approval=requires_human, triggered_by=TaskTrigger.agent_self,
        result=result,
        completed_at=datetime.utcnow() if status == TaskStatus.completed else None,
    )
    db.add(t)
    db.commit()
    db.refresh(t)
    return t


def daily_briefing(db: Session, agent_id: str) -> dict:
    agent = _agent(db, agent_id)
    if not agent:
        return {"error": "agent_not_found"}
    events = calendar_service.list_events(db, agent.user_id, days_ahead=2, max_results=20)
    prompt = (
        f"Today {agent.user.name} has these events: {json.dumps(events)}\n"
        f"Write a brief morning briefing (3-4 sentences). Flag back-to-back "
        f"meetings, prep needed, conflicts. Be direct, not cheerful."
    )
    briefing = generate(prompt, response_format="briefing")
    t = _task(
        db, agent, "Daily briefing",
        f"Briefing for {datetime.utcnow():%Y-%m-%d}", TaskType.analysis,
        {"summary": briefing, "result": briefing, "events": events},
    )
    log_event(logger, "daily_briefing", agent_id=agent.id, task=t.id)
    return {"task_id": t.id, "briefing": briefing}


def find_and_book_slot(db: Session, agent_id: str, with_email: str,
                       purpose: str, duration_minutes: int = 30) -> dict:
    agent = _agent(db, agent_id)
    if not agent:
        return {"error": "agent_not_found"}
    slots = []
    for d in range(1, 6):
        day = datetime.utcnow() + timedelta(days=d)
        if day.weekday() >= 5:
            continue
        slots.extend(
            calendar_service.find_free_slots(
                db, agent.user_id, day.strftime("%Y-%m-%d"), duration_minutes
            )[:2]
        )
    proposed = slots[:3]
    t = _task(
        db, agent, f"Book: {purpose[:50]}",
        f"Proposed slots with {with_email} for {purpose}", TaskType.scheduling,
        {"summary": f"Proposed {len(proposed)} slots — approve to book + send invite",
         "result": {"proposed_slots": proposed, "with_email": with_email,
                     "purpose": purpose, "duration": duration_minutes}},
        status=TaskStatus.awaiting_human, requires_human=True,
    )
    return {"task_id": t.id, "proposed_slots": proposed}


def confirm_booking(db: Session, agent_id: str, task_id: str) -> dict:
    """Called after a find_and_book_slot task is approved — creates the event."""
    agent = _agent(db, agent_id)
    t = db.query(Task).filter(Task.id == task_id, Task.agent_id == agent.id).first()
    if not t or not t.result:
        return {"error": "task_not_found"}
    info = (t.result or {}).get("result", {})
    slot = (info.get("proposed_slots") or [{}])[0]
    if not slot:
        return {"error": "no_slot"}
    ev = calendar_service.create_event(
        db, agent.user_id, summary=info.get("purpose", "Meeting"),
        start_dt=slot["start"], end_dt=slot["end"],
        attendees=[info.get("with_email")], add_meet_link=True,
    )
    return {"event_id": ev["id"], "meet_link": ev.get("meet_link", "")}


def reschedule_event(db: Session, agent_id: str, event_id: str, reason: str) -> dict:
    agent = _agent(db, agent_id)
    if not agent:
        return {"error": "agent_not_found"}
    ev = calendar_service.get_event(db, agent.user_id, event_id)
    alt = []
    for d in range(1, 5):
        day = datetime.utcnow() + timedelta(days=d)
        if day.weekday() >= 5:
            continue
        alt.extend(
            calendar_service.find_free_slots(db, agent.user_id,
                                             day.strftime("%Y-%m-%d"), 30)[:2]
        )
    alt = alt[:3]
    attendees = [a["email"] for a in ev.get("attendees", [])]
    prompt = (
        f"Write a polite email rescheduling '{ev['summary']}'. Reason: {reason}. "
        f"Propose these alternatives: {alt}. Return only the body."
    )
    body = generate(prompt, response_format="schedule_email")
    draft_id = gmail_service.draft_email(
        db, agent.user_id, to=",".join(attendees) or "attendees@example.com",
        subject=f"Rescheduling: {ev['summary']}", body=body,
    )
    t = _task(
        db, agent, f"Reschedule: {ev['summary'][:50]}",
        f"Reschedule draft + alternatives ({reason})", TaskType.scheduling,
        {"summary": "Reschedule drafted — approve to send + move the event",
         "result": body, "draft_id": draft_id, "event_id": event_id,
         "alternatives": alt},
        status=TaskStatus.awaiting_human, requires_human=True,
    )
    return {"task_id": t.id, "draft_id": draft_id, "alternatives": alt}


def prep_for_meeting(db: Session, agent_id: str, event_id: str) -> dict:
    agent = _agent(db, agent_id)
    if not agent:
        return {"error": "agent_not_found"}
    ev = calendar_service.get_event(db, agent.user_id, event_id)
    prior = []
    for a in ev.get("attendees", [])[:3]:
        prior.extend(
            gmail_service.search_emails(db, agent.user_id,
                                        f"from:{a['email']} OR to:{a['email']}",
                                        max_results=3)
        )
    prompt = (
        f"Prepare a 5-bullet meeting prep note for {agent.user.name}.\n"
        f"Event: {ev['summary']} — {ev.get('description','')}\n"
        f"Attendees: {[a['email'] for a in ev.get('attendees', [])]}\n"
        f"Prior email context: {json.dumps(prior)[:1500]}\nReturn JSON {{bullets:[...]}}."
    )
    raw = generate(prompt, response_format="meeting_prep")
    try:
        prep = json.loads(raw)
    except (json.JSONDecodeError, TypeError):
        prep = {"bullets": [raw]}
    t = _task(
        db, agent, f"Prep: {ev['summary'][:50]}",
        f"Meeting prep for {ev['summary']}", TaskType.analysis,
        {"summary": f"Prep ready for {ev['summary']}", "result": prep,
         "event_id": event_id},
    )
    return {"task_id": t.id, "prep": prep}
