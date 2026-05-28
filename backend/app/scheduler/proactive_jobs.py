"""Proactive agent behaviors that run on a schedule.

Three jobs, all gated by per-agent `scheduled_jobs.enabled`:

  morning_briefing_post  — daily 8am: post a calendar+inbox briefing to feed.
  inbox_monitor_sweep    — every 30 min: alert on urgent/VIP emails, deduped.
  auto_post_sweep        — daily 9am: post a fresh take in the agent's voice
                            if its auto_post_schedule says daily/weekly.

Every Gemini call here routes through services.gemini.generate_for_agent so the
agent's persistent voice (bio + system_prompt + personality) is injected.

Resilience contract (Hardening sprint):
- Each sweep wraps its outer body and every per-agent iteration in
  try/except so one agent's failure never aborts the rest.
- Failures stamp last_error / last_error_at on the relevant scheduled_jobs
  row and log via logger.error(..., exc_info=True).
- Gemini quota / 503 / rate-limit failures degrade gracefully: instead of
  silence, the agent posts a `post_type="system_notice"` placeholder so
  the user sees something in the feed and knows it'll retry next run.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.logging import get_logger, log_event
from app.models import Agent, AgentAlert, AgentPost, GhostPost, ScheduledJob
from app.models.agent import AgentMemory, AgentMemoryType
from app.services import calendar_service, gmail_service
from app.services.gemini import generate_for_agent
from app.services.scheduler_service import (
    auto_post_should_run_today,
    enabled_agents_for,
    mark_ran,
)
from app.scheduler.lock import job_lock

logger = get_logger("axolot.proactive")

JOB_MORNING_BRIEFING = "morning_briefing"
JOB_INBOX_MONITOR = "inbox_monitor"
JOB_AUTO_POST = "auto_post"
JOB_GHOST_POST = "ghost_post"

# Minimum hours between an agent's ghost posts. The sweep fires every 4-6h
# (jittered), but this is the hard floor that keeps an agent from posting twice
# in quick succession if a run is delayed/coalesced — "natural, not spammy".
GHOST_MIN_GAP_HOURS = 4

# Heuristics — kept here, not config, because they're product decisions.
VIP_MIN_THREADS = 5             # contacts you've gotten >=5 messages from are "VIP"
URGENT_KEYWORDS = ("urgent", "asap", "today", "deadline")
POST_MAX_CHARS = 500            # mirror the agent_posts schema cap

# Substrings that mark a transient Gemini-side failure where the right move is
# a "we'll retry next run" notice, not bubbling the exception. Matched against
# the exception's repr/str — works for both the typed
# google.api_core.exceptions.GoogleAPIError family and any wrapper.
_GEMINI_TRANSIENT_MARKERS = ("quota", "503", "rate", "ResourceExhausted",
                             "ServiceUnavailable", "DeadlineExceeded")

SYSTEM_NOTICE_TEXT = (
    "⚠ Your agent couldn't post this morning due to a temporary error. "
    "It will retry next scheduled run."
)


# ── Helpers ────────────────────────────────────────────────────────────────
def _looks_like_gemini_transient(exc: BaseException) -> bool:
    """True for the kind of Gemini error worth degrading-with-a-notice on."""
    try:
        from google.api_core import exceptions as gae  # type: ignore

        if isinstance(exc, gae.GoogleAPIError):
            return True
    except ImportError:  # google libs not installed in test/stub mode
        pass
    msg = f"{type(exc).__name__}: {exc}"
    return any(m.lower() in msg.lower() for m in _GEMINI_TRANSIENT_MARKERS)


def _record_sweep_error(db: Session, agent_id: str, job_type: str, exc: BaseException) -> None:
    """Stamp the error onto the scheduled_jobs row. Best-effort — never raises."""
    try:
        row = (
            db.query(ScheduledJob)
            .filter(
                ScheduledJob.agent_id == agent_id,
                ScheduledJob.job_type == job_type,
            )
            .first()
        )
        if row:
            row.last_error = f"{type(exc).__name__}: {exc}"[:1000]
            row.last_error_at = datetime.utcnow()
            db.commit()
    except Exception:  # noqa: BLE001
        db.rollback()


def _post(
    db: Session,
    agent: Agent,
    content: str,
    *,
    post_type: str = "standard",
    record_memory: bool = True,
) -> AgentPost:
    """Drop a post on the agent's feed — same shape as POST /agents/{id}/post.

    `record_memory=False` for system notices, so the agent's voice memory
    doesn't get polluted with "[posted] couldn't post".
    """
    post = AgentPost(
        agent_id=agent.id,
        content=content[:POST_MAX_CHARS].strip(),
        post_type=post_type,
    )
    db.add(post)
    if record_memory:
        db.add(
            AgentMemory(
                agent_id=agent.id,
                memory_type=AgentMemoryType.post_history,
                content=f"[posted] {content[:300]}",
                importance_score=0.5,
            )
        )
    db.commit()
    db.refresh(post)
    return post


def _post_system_notice(db: Session, agent: Agent) -> None:
    """Best-effort placeholder when Gemini is down. Failures here are
    swallowed silently — we already logged the original exception."""
    try:
        _post(db, agent, SYSTEM_NOTICE_TEXT, post_type="system_notice",
              record_memory=False)
    except Exception:  # noqa: BLE001
        db.rollback()


def _run(job_id: str, fn) -> None:
    with job_lock(job_id) as acquired:
        if not acquired:
            log_event(logger, "job_skipped_locked", job=job_id)
            return
        log_event(logger, "job_start", job=job_id)
        try:
            fn()
            log_event(logger, "job_done", job=job_id)
        except Exception as exc:  # noqa: BLE001
            log_event(logger, "job_error", job=job_id, error=str(exc))
            logger.error(f"[{job_id}] sweep aborted: {exc}", exc_info=True)


def _handle_agent_failure(
    db: Session,
    agent: Agent,
    job_type: str,
    sweep_name: str,
    exc: BaseException,
) -> None:
    """One agent's iteration failed. Log, stamp, and (if it's a Gemini
    transient) post a system_notice so the user isn't met with silence."""
    logger.error(
        f"[{sweep_name}] agent_id={agent.id} failed: {exc}", exc_info=True
    )
    _record_sweep_error(db, agent.id, job_type, exc)
    if _looks_like_gemini_transient(exc):
        _post_system_notice(db, agent)


# ── Morning briefing ────────────────────────────────────────────────────────
def morning_briefing_post():
    """8am daily — for every agent with the behavior enabled AND a connected
    integration, generate a one-paragraph briefing combining today's calendar
    and top-5 unread emails, then post it to the agent's feed."""

    def _do():
        db = SessionLocal()
        try:
            try:
                agents = enabled_agents_for(db, JOB_MORNING_BRIEFING)
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    f"[morning_briefing_post] enabled_agents lookup failed: {exc}",
                    exc_info=True,
                )
                return
            for agent in agents:
                try:
                    user = agent.user
                    if not user or not (user.gmail_connected or user.calendar_connected):
                        continue
                    events = (
                        calendar_service.list_events(db, user.id, days_ahead=1, max_results=10)
                        if user.calendar_connected
                        else []
                    )
                    emails = (
                        gmail_service.list_emails(
                            db, user.id, max_results=5, unread_only=True
                        )
                        if user.gmail_connected
                        else []
                    )
                    if not events and not emails:
                        continue
                    email_brief = [
                        {
                            "subject": e["subject"],
                            "from": e["sender"],
                            "snippet": e["snippet"][:140],
                        }
                        for e in emails
                    ]
                    instruction = (
                        "Compose a short morning briefing post (3-4 sentences) for "
                        f"{user.name}, written in your own voice as their agent. "
                        "Weave today's calendar and the most important unread email "
                        "into one natural paragraph — not a list. Be direct, not "
                        "cheerful.\n\n"
                        f"Today's calendar: {json.dumps(events)}\n\n"
                        f"Top unread emails: {json.dumps(email_brief)}"
                    )
                    text = (generate_for_agent(db, agent, instruction) or "").strip()
                    if not text:
                        continue
                    _post(db, agent, text)
                    mark_ran(db, agent.id, JOB_MORNING_BRIEFING)
                    log_event(logger, "morning_briefing_posted", agent_id=agent.id)
                except Exception as exc:  # noqa: BLE001
                    db.rollback()
                    _handle_agent_failure(
                        db, agent, JOB_MORNING_BRIEFING,
                        "morning_briefing_post", exc,
                    )
        finally:
            db.close()

    _run("morning_briefing_post", _do)


# ── Inbox monitor ───────────────────────────────────────────────────────────
def _vip_senders(emails: list[dict]) -> set[str]:
    """A sender is VIP if they appear >= VIP_MIN_THREADS times in the recent
    inbox window — a cheap signal for the people the user actually corresponds
    with."""
    return {
        e
        for e, n in Counter(em["sender_email"] for em in emails).items()
        if n >= VIP_MIN_THREADS
    }


def _is_urgent(email: dict, vips: set[str]) -> tuple[bool, str | None]:
    """(is_urgent, alert_type). Marked urgent by Gmail label, urgent keyword in
    subject, OR from a VIP sender."""
    if email.get("is_read"):
        return False, None
    labels = {l.upper() for l in (email.get("labels") or [])}
    subject = (email.get("subject") or "").lower()
    if "IMPORTANT" in labels or any(k in subject for k in URGENT_KEYWORDS):
        return True, "urgent_email"
    if email.get("sender_email") in vips:
        return True, "vip_email"
    return False, None


def inbox_monitor_sweep():
    """Every 30 min — alert on urgent/VIP unread emails, never twice for the
    same message_id (agent_alerts unique-constraint enforces it)."""

    def _do():
        db = SessionLocal()
        try:
            try:
                agents = enabled_agents_for(db, JOB_INBOX_MONITOR)
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    f"[inbox_monitor_sweep] enabled_agents lookup failed: {exc}",
                    exc_info=True,
                )
                return
            for agent in agents:
                try:
                    user = agent.user
                    if not user or not user.gmail_connected:
                        continue
                    recent = gmail_service.list_emails(db, user.id, max_results=40)
                    vips = _vip_senders(recent)
                    unread = [e for e in recent if not e.get("is_read")]
                    if not unread:
                        continue

                    alerted: list[dict] = []
                    for em in unread[:10]:
                        is_urg, alert_type = _is_urgent(em, vips)
                        if not is_urg:
                            continue
                        existing = (
                            db.query(AgentAlert)
                            .filter(
                                AgentAlert.agent_id == agent.id,
                                AgentAlert.message_id == em["id"],
                            )
                            .first()
                        )
                        if existing:
                            continue
                        db.add(
                            AgentAlert(
                                agent_id=agent.id,
                                message_id=em["id"],
                                alert_type=alert_type,
                            )
                        )
                        alerted.append({**em, "alert_type": alert_type})
                    if not alerted:
                        continue
                    db.commit()

                    if len(alerted) == 1:
                        em = alerted[0]
                        tag = "VIP" if em["alert_type"] == "vip_email" else "Urgent"
                        instruction = (
                            f"In one short sentence as {user.name}'s agent, flag this "
                            f"newly-arrived {tag} email — what it is and who from. "
                            f"No preamble.\n\nEmail: from {em['sender']} "
                            f"<{em['sender_email']}>, subject '{em['subject']}'."
                        )
                    else:
                        summary = "\n".join(
                            f"- {em['alert_type']}: '{em['subject']}' from {em['sender']}"
                            for em in alerted
                        )
                        instruction = (
                            f"In one short paragraph as {user.name}'s agent, flag "
                            f"these newly-arrived urgent/VIP emails. Keep it under "
                            f"80 words.\n\n{summary}"
                        )
                    text = (generate_for_agent(db, agent, instruction) or "").strip()
                    if text:
                        _post(db, agent, text)
                        log_event(
                            logger, "inbox_monitor_posted",
                            agent_id=agent.id, alerts=len(alerted),
                        )
                    mark_ran(db, agent.id, JOB_INBOX_MONITOR)
                except Exception as exc:  # noqa: BLE001
                    db.rollback()
                    _handle_agent_failure(
                        db, agent, JOB_INBOX_MONITOR,
                        "inbox_monitor_sweep", exc,
                    )
        finally:
            db.close()

    _run("inbox_monitor_sweep", _do)


# ── Auto post ───────────────────────────────────────────────────────────────
def auto_post_sweep():
    """9am — for every agent set to daily/weekly auto_post, generate one post
    in the agent's voice using its bio + recent post history. Skipped silently
    on a weekly schedule any day except Monday."""

    def _do():
        db = SessionLocal()
        try:
            try:
                agents = enabled_agents_for(db, JOB_AUTO_POST)
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    f"[auto_post_sweep] enabled_agents lookup failed: {exc}",
                    exc_info=True,
                )
                return
            today = datetime.utcnow()
            for agent in agents:
                try:
                    if not auto_post_should_run_today(
                        agent.auto_post_schedule or "off", today
                    ):
                        continue
                    recent = (
                        db.query(AgentPost)
                        .filter(AgentPost.agent_id == agent.id)
                        .order_by(AgentPost.created_at.desc())
                        .limit(5)
                        .all()
                    )
                    recent_text = (
                        "\n".join(f"- {p.content}" for p in recent)
                        if recent
                        else "(no prior posts)"
                    )
                    instruction = (
                        "Write one fresh post (2-4 sentences, under 500 chars) for "
                        "your feed, in your own voice. The topic should reflect "
                        "your bio and your user's recent interests. Don't repeat "
                        "anything from your last posts. No hashtags, no quotes "
                        f"around the post.\n\nYour last posts:\n{recent_text}"
                    )
                    text = (generate_for_agent(db, agent, instruction) or "").strip()
                    if not text:
                        continue
                    _post(db, agent, text)
                    mark_ran(db, agent.id, JOB_AUTO_POST)
                    log_event(logger, "auto_post_posted", agent_id=agent.id)
                except Exception as exc:  # noqa: BLE001
                    db.rollback()
                    _handle_agent_failure(
                        db, agent, JOB_AUTO_POST, "auto_post_sweep", exc,
                    )
        finally:
            db.close()

    _run("auto_post_sweep", _do)


# ── Ghost posting ────────────────────────────────────────────────────────────
def ghost_post_sweep():
    """Every 4-6h (jittered) — for every agent that opted into ghost posting,
    generate one post in the owner's voice grounded in their memory, rotating
    through the four categories. Enforces a per-agent minimum gap so a delayed or
    coalesced run can't double-post.

    Same resilience contract as the other sweeps: per-agent try/except, error
    stamped onto the scheduled_jobs row, Gemini transients degrade to a notice.
    """
    from app.services.ghost_post_engine import generate_ghost_post

    def _do():
        db = SessionLocal()
        try:
            try:
                agents = enabled_agents_for(db, JOB_GHOST_POST)
            except Exception as exc:  # noqa: BLE001
                logger.error(
                    f"[ghost_post_sweep] enabled_agents lookup failed: {exc}",
                    exc_info=True,
                )
                return
            gap_cutoff = datetime.utcnow() - timedelta(hours=GHOST_MIN_GAP_HOURS)
            for agent in agents:
                try:
                    if not agent.user:
                        continue
                    last = (
                        db.query(GhostPost.generated_at)
                        .filter(GhostPost.agent_id == agent.id)
                        .order_by(GhostPost.generated_at.desc())
                        .first()
                    )
                    if last and last[0] and last[0] > gap_cutoff:
                        continue  # posted too recently — let it breathe
                    ghost = generate_ghost_post(db, agent)
                    if ghost:
                        mark_ran(db, agent.id, JOB_GHOST_POST)
                        log_event(
                            logger, "ghost_post_posted",
                            agent_id=agent.id, post_type=ghost.post_type,
                        )
                except Exception as exc:  # noqa: BLE001
                    db.rollback()
                    _handle_agent_failure(
                        db, agent, JOB_GHOST_POST, "ghost_post_sweep", exc,
                    )
        finally:
            db.close()

    _run("ghost_post_sweep", _do)


def register_proactive_jobs(scheduler) -> None:
    """Wire the proactive sweeps into APScheduler. Idempotent — every job is
    added with replace_existing so restart is safe."""
    scheduler.add_job(
        morning_briefing_post, "cron", hour=8, minute=0,
        id="morning_briefing_post", replace_existing=True,
    )
    scheduler.add_job(
        inbox_monitor_sweep, "interval", minutes=30,
        id="inbox_monitor_sweep", replace_existing=True,
    )
    scheduler.add_job(
        auto_post_sweep, "cron", hour=9, minute=0,
        id="auto_post_sweep", replace_existing=True,
    )
    # Ghost posting — base 5h interval with ±1h jitter (=> 4-6h) so agents don't
    # all post at the same synchronized instant.
    scheduler.add_job(
        ghost_post_sweep, "interval", hours=5, jitter=3600,
        id="ghost_post_sweep", replace_existing=True,
    )
