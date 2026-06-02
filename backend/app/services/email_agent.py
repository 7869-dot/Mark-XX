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
from app.models import Agent, AgentTaskResult, ClassifiedEmail, User
from app.models.agent import AgentRole
from app.models.email_classification import EmailCategory
from app.schemas.jarvis import AgentTask
from app.services.agent_runs import EMAIL_AGENT, log_run

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


def run_report(db: Session, user: User, *, limit: int = 40) -> dict:
    """Summarise the user's inbox state by priority for Jarvis.

    Reads persisted ClassifiedEmail verdicts (Gmail content stays in Gmail) and
    buckets them: urgent_human -> urgent, agent_handleable -> important (carries
    a pre-drafted reply + an action flag), informational -> low, spam dropped.
    Returns a structured JSON summary. Never raises; logs an AgentRunLog row.
    Leaves a TODO for live IMAP for non-Gmail inboxes.
    """
    # Bug 3: if Google is disconnected (e.g. an expired/revoked refresh token),
    # don't attempt any Gmail read — skip cleanly and surface the reconnect need.
    from app.services import google_auth

    if not google_auth.is_connected(user):
        log_event(logger, "email_agent_skipped", user_id=user.id, reason="google_disconnected")
        log_run(db, user.id, EMAIL_AGENT,
                "Skipped — Google disconnected; reconnect to triage your inbox.", status="skipped")
        return {
            "connected": False,
            "skipped": True,
            "reason": "google_disconnected",
            "urgent": [], "important": [], "low": [], "action_required": [],
            "counts": {"urgent": 0, "important": 0, "low": 0},
        }

    rows = (
        db.query(ClassifiedEmail)
        .filter(ClassifiedEmail.user_id == user.id, ClassifiedEmail.dismissed.is_(False))
        .order_by(ClassifiedEmail.created_at.desc())
        .limit(limit)
        .all()
    )
    urgent, important, low, action_required = [], [], [], []
    for e in rows:
        cat = e.category.value if hasattr(e.category, "value") else str(e.category)
        item = {"subject": e.subject, "from": e.sender or e.sender_email}
        if cat == EmailCategory.urgent_human.value:
            urgent.append(item)
            action_required.append(item)
        elif cat == EmailCategory.agent_handleable.value:
            item["suggested_reply"] = (e.drafted_reply or "")[:400]
            important.append(item)
            action_required.append(item)
        elif cat == EmailCategory.informational.value:
            low.append(item)
        # spam is intentionally dropped from the briefing.

    connected = bool(getattr(user, "gmail_connected", False))
    summary_line = (
        f"{len(urgent)} urgent, {len(important)} need action, {len(low)} low-priority."
        if rows else
        ("Inbox is clear." if connected else "Gmail not connected — no inbox to triage.")
    )
    log_run(db, user.id, EMAIL_AGENT, summary_line, status="ok")
    log_event(logger, "email_report", user_id=user.id, urgent=len(urgent), important=len(important))
    return {
        "connected": connected,
        "urgent": urgent,
        "important": important,
        "low": low,
        "action_required": action_required,
        "counts": {"urgent": len(urgent), "important": len(important), "low": len(low)},
        # TODO: live IMAP fetch path for non-Gmail inboxes (Gmail OAuth done first).
    }
