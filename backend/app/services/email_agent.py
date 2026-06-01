"""Email agent execution — drafts replies on Jarvis's instruction.

Sprint 2 scope: one task type — "draft a reply". The agent reasons in the
user's voice (via the email agent's persona + context_builder), produces a
draft, and stores it for explicit approval. It NEVER sends: requires_approval is
hardcoded True and there is no send path in V1.
"""
from __future__ import annotations

import json
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.logging import get_logger, log_event
from app.models import Agent, AgentTaskResult, ClassifiedEmail
from app.models.agent import AgentRole
from app.schemas.jarvis import AgentTask

logger = get_logger("axolot.email_agent")


def _email_agent(db: Session, user_id: str) -> Agent | None:
    return (
        db.query(Agent)
        .filter(Agent.user_id == user_id, Agent.role == AgentRole.email.value)
        .first()
    )


def _thread_context(db: Session, user_id: str) -> str:
    """Lightweight thread context: the most recent classified email, if any.
    Full OAuth thread fetch is Sprint 3 — for now we ground on what we have."""
    e = (
        db.query(ClassifiedEmail)
        .filter(ClassifiedEmail.user_id == user_id)
        .order_by(ClassifiedEmail.created_at.desc())
        .first()
    )
    if not e:
        return ""
    return f"From {e.sender} — subject '{e.subject}': {e.snippet}"


def execute_task(db: Session, task: AgentTask, user_id: str) -> AgentTaskResult | None:
    """Execute a Jarvis-assigned email task. Returns the stored draft row, or
    None if there's no email agent. Best-effort — never raises into the caller."""
    if task.agent_role != "email":
        return None
    agent = _email_agent(db, user_id)
    if not agent:
        return None

    thread = _thread_context(db, user_id)
    instruction = (
        "Jarvis assigned you this task: \"" + task.task_description + "\".\n"
        "Draft a reply email in your user's voice — natural, specific, not a "
        "generic assistant tone. " + (f"Relevant thread: {thread}\n" if thread else "")
        + "Return ONLY valid JSON with keys: subject_line, recipient_hint "
        "(who it's likely for), draft_content (the email body). No preamble."
    )
    try:
        from app.services.gemini import generate_for_agent

        raw = generate_for_agent(db, agent, instruction, response_format="email_draft")
        data = json.loads(raw)
        subject = str(data.get("subject_line", "")).strip()[:500]
        recipient = str(data.get("recipient_hint", "")).strip()[:200]
        body = str(data.get("draft_content", "")).strip()
    except Exception as exc:  # noqa: BLE001
        log_event(logger, "email_draft_failed", user_id=user_id, error=str(exc))
        return None

    if not body:
        return None

    result = AgentTaskResult(
        user_id=user_id,
        task_id=getattr(task, "task_id", None) or _new_task_id(),
        agent_role="email",
        draft_content=body,
        subject_line=subject or "Draft",
        recipient_hint=recipient or "—",
        requires_approval=True,   # ALWAYS True in V1 — the agent never sends.
        approved=None,
    )
    db.add(result)
    db.commit()
    db.refresh(result)
    log_event(logger, "email_draft_created", user_id=user_id, result_id=result.id)
    return result


def _new_task_id() -> str:
    import uuid

    return str(uuid.uuid4())
