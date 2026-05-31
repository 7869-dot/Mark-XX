"""Privacy is structural, not a policy — it's enforced here, in code.

Every byte that leaves one agent's context for another passes through this
middleware. It (1) strips PII from text, (2) derives *anonymized intent signals*
from a user's worldview without ever exposing the worldview itself, and (3)
writes a privacy_audit_log row so the owner can see exactly what their agent
shared and why.

Guiding test for every path here: "Would the user be proud if they saw exactly
what their agent did and why?"
"""
import re
from datetime import datetime

from sqlalchemy.orm import Session

from app.core.logging import get_logger, log_event
from app.models import Agent, PrivacyAuditLog

logger = get_logger("axolot.privacy")

_EMAIL = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_PHONE = re.compile(r"(?<!\w)(?:\+?\d[\d\s().-]{7,}\d)(?!\w)")
_URL = re.compile(r"https?://\S+")
_HANDLE = re.compile(r"(?<!\w)@[A-Za-z0-9_]{2,}")


def strip_pii(text: str, names: list[str] | None = None) -> str:
    """Redact emails, phone numbers, URLs, @handles and any supplied names.

    Used as the safety net on anything crossing an agent boundary — intent
    signals are also PII-free by construction, but we never rely on the model
    for that.
    """
    if not text:
        return ""
    out = _EMAIL.sub("[redacted]", text)
    out = _PHONE.sub("[redacted]", out)
    out = _URL.sub("[link]", out)
    out = _HANDLE.sub("[redacted]", out)
    for n in names or []:
        n = (n or "").strip()
        if len(n) >= 2:
            out = re.sub(rf"\b{re.escape(n)}\b", "someone", out, flags=re.IGNORECASE)
    return out.strip()


def audit(
    db: Session,
    actor_agent: Agent | None,
    subject_user_id: str | None,
    action: str,
    reason: str,
    metadata: dict | None = None,
    *,
    commit: bool = True,
) -> PrivacyAuditLog | None:
    """Record an action that touched another user's data. Never raises."""
    try:
        row = PrivacyAuditLog(
            actor_agent_id=actor_agent.id if actor_agent else None,
            actor_user_id=actor_agent.user_id if actor_agent else None,
            subject_user_id=subject_user_id,
            action=action,
            reason=(reason or "")[:1000],
            audit_metadata=metadata or {},
        )
        db.add(row)
        if commit:
            db.commit()
        return row
    except Exception as exc:  # noqa: BLE001
        log_event(logger, "privacy_audit_failed", action=action, error=str(exc))
        try:
            db.rollback()
        except Exception:  # noqa: BLE001
            pass
        return None


def derive_intent_signal(db: Session, agent: Agent) -> str:
    """Turn the user's worldview into a shareable, PII-free intent signal.

    The PersonalityMatrix never leaves the agent's context — only this derived
    one-liner ("Someone is looking for a backend co-founder") is ever shared.
    """
    from app.services.gemini import generate_for_agent

    goals = agent.goal_titles or []
    interests = (agent.core_interests or agent.interest_tags or [])[:6]
    instruction = (
        "In ONE sentence, state what you're looking for from the network right "
        "now, on your user's behalf — a collaborator, a peer, an exchange of "
        "ideas. CRITICAL: no names, no companies, no emails, no identifying "
        "details — start with 'Someone' and describe only the intent and the "
        "kind of person. Example: 'Someone is looking for a backend co-founder "
        "for an early-stage AI product.'\n\n"
        f"Your user's goals: {goals}\nYour user's interests: {interests}"
    )
    raw = (generate_for_agent(db, agent, instruction, response_format="intent_signal") or "").strip()
    # Safety net — never trust the model with PII; also scrub both names.
    names = [n for n in [(agent.user.name if agent.user else None), agent.name] if n]
    signal = strip_pii(raw.strip('"').strip(), names=names)
    return signal or "Someone is looking to connect with like-minded people."
