"""Gmail intelligence — classify recent emails into URGENT_HUMAN, INFORMATIONAL,
SPAM, AGENT_HANDLEABLE; pre-draft replies for AGENT_HANDLEABLE rows.

Email bodies are NEVER persisted. We only store the verdict + drafted reply.
"""
import json
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.logging import get_logger, log_event
from app.models import (
    ActivityType,
    Agent,
    ClassifiedEmail,
    EmailCategory,
    User,
)
from app.services import gmail_service
from app.services.gemini import generate
from app.services.activity_logger import log_activity

logger = get_logger("axolot.email_classifier")

_CLASSIFY_PROMPT = """Classify this email. Categories:
- URGENT_HUMAN: requires the user's direct decision or response within 24h
- INFORMATIONAL: newsletter, update, notification — no action needed
- SPAM: unsolicited, promotional, irrelevant
- AGENT_HANDLEABLE: routine reply, scheduling, confirmation the agent can draft automatically

Email subject: {subject}
Email from: {sender}
Email preview: {preview}

Return JSON: {{"category": "...", "reason": "...", "suggested_action": "..."}}
"""

_DRAFT_PROMPT = """You are {agent_name}, drafting a reply on behalf of {user_name}.

Mirror {user_name}'s voice — same vocabulary, tone, and sentence length. Do not
sound like an AI. Output ONLY the email body. No subject line, no signature.

Email you're replying to:
From: {sender}
Subject: {subject}
Preview: {preview}

Suggested action: {suggested_action}

Reply now, as {user_name} would:"""


def _heuristic_classify(subject: str, sender: str, snippet: str) -> dict:
    """Fallback when Gemini is unavailable or returns garbage.

    Keeps the surface working in dev / stub mode without an LLM call. The
    rules are intentionally simple — better to err on UR­GENT_HUMAN than to
    silently archive something that matters.
    """
    s = (subject + " " + snippet + " " + sender).lower()
    spam_markers = ("unsubscribe", "promotion", "newsletter", "no-reply", "noreply",
                    "digest@", "marketing")
    if any(m in s for m in spam_markers):
        return {
            "category": "INFORMATIONAL",
            "reason": "Matched newsletter/marketing markers.",
            "suggested_action": "No action needed.",
        }
    urgent_markers = ("urgent", "asap", "today", "tomorrow", "deadline",
                      "due fri", "due mon", "due tue", "contract", "review",
                      "invoice", "payment")
    if any(m in s for m in urgent_markers):
        return {
            "category": "URGENT_HUMAN",
            "reason": "Time-sensitive language detected.",
            "suggested_action": "Review and respond directly.",
        }
    scheduling_markers = ("coffee", "meeting", "schedule", "reschedule",
                          "available", "free thursday", "free friday", "calendar")
    if any(m in s for m in scheduling_markers):
        return {
            "category": "AGENT_HANDLEABLE",
            "reason": "Looks like a scheduling exchange the agent can draft.",
            "suggested_action": "Propose available slots from the user's calendar.",
        }
    return {
        "category": "INFORMATIONAL",
        "reason": "No urgent or actionable markers detected.",
        "suggested_action": "No action needed.",
    }


def classify_one(
    db: Session,
    user: User,
    agent: Agent | None,
    email_meta: dict,
) -> ClassifiedEmail | None:
    """Classify a single email and persist the verdict. Idempotent on email_id."""
    eid = email_meta.get("id")
    if not eid:
        return None
    existing = (
        db.query(ClassifiedEmail)
        .filter(ClassifiedEmail.user_id == user.id, ClassifiedEmail.email_id == eid)
        .first()
    )
    if existing:
        return existing

    subject = email_meta.get("subject", "")
    sender = email_meta.get("sender", "")
    sender_email = email_meta.get("sender_email", "")
    preview = (email_meta.get("snippet", "") or "")[:300]

    prompt = _CLASSIFY_PROMPT.format(subject=subject, sender=sender, preview=preview)
    raw = generate(prompt, response_format="text")
    verdict: dict
    try:
        # Defensive — strip code fences if Gemini wrapped the JSON.
        clean = raw.strip().strip("`")
        if clean.startswith("json"):
            clean = clean[4:].strip()
        verdict = json.loads(clean)
        assert verdict.get("category") in {c.value for c in EmailCategory}
    except (json.JSONDecodeError, AssertionError, AttributeError, TypeError):
        verdict = _heuristic_classify(subject, sender, preview)

    try:
        category = EmailCategory(verdict.get("category"))
    except ValueError:
        category = EmailCategory.informational

    drafted_reply = None
    if category == EmailCategory.agent_handleable and agent:
        # Draft the reply now so the user sees it immediately on next dashboard
        # load. Voice-matched via the personality the chat prompt is trained on.
        draft_prompt = _DRAFT_PROMPT.format(
            agent_name=agent.name,
            user_name=user.name,
            sender=sender,
            subject=subject,
            preview=preview,
            suggested_action=verdict.get("suggested_action", ""),
        )
        drafted_reply = (generate(draft_prompt, response_format="email_reply") or "").strip()

    row = ClassifiedEmail(
        user_id=user.id,
        agent_id=agent.id if agent else None,
        email_id=eid,
        thread_id=email_meta.get("thread_id"),
        sender=sender,
        sender_email=sender_email,
        subject=subject,
        snippet=preview,
        category=category,
        reason=str(verdict.get("reason", ""))[:500],
        suggested_action=str(verdict.get("suggested_action", ""))[:500],
        drafted_reply=drafted_reply,
        draft_status="pending" if drafted_reply else "pending",
    )
    db.add(row)
    db.commit()
    db.refresh(row)

    if agent:
        log_activity(
            db, agent.id, ActivityType.email_classified,
            f"Classified email from {sender or 'unknown'} as {category.value}.",
            metadata={"email_id": eid, "category": category.value},
        )
        if drafted_reply:
            log_activity(
                db, agent.id, ActivityType.email_drafted,
                f"Drafted a reply to {sender or 'unknown'} — awaiting your approval.",
                metadata={"email_id": eid},
            )
    return row


def classify_recent_for_user(db: Session, user: User, hours: int = 48, max_emails: int = 25) -> int:
    """Pull recent inbox emails and classify each. Returns count classified."""
    if not getattr(user, "gmail_connected", False):
        return 0
    agent = next((a for a in user.agents if a.is_primary), None) or (
        user.agents[0] if user.agents else None
    )
    try:
        emails = gmail_service.list_emails(
            db, user.id, max_results=max_emails, unread_only=False
        )
    except Exception as exc:  # noqa: BLE001
        log_event(logger, "classify_list_failed", user_id=user.id, error=str(exc))
        return 0

    cutoff = datetime.utcnow() - timedelta(hours=hours)
    count = 0
    for em in emails:
        # Skip rows older than the lookback window when a parseable date exists.
        date_str = em.get("date", "")
        try:
            ts = datetime.fromisoformat(date_str.replace("Z", ""))
            if ts < cutoff:
                continue
        except (ValueError, TypeError):
            pass
        if classify_one(db, user, agent, em) is not None:
            count += 1
    log_event(logger, "classify_run", user_id=user.id, classified=count)
    return count
