"""Proactive agent behaviors that run on a schedule.

Three jobs, all gated by per-agent `scheduled_jobs.enabled`:

  morning_briefing_post  — daily 8am: post a calendar+inbox briefing to feed.
  inbox_monitor_sweep    — every 30 min: alert on urgent/VIP emails, deduped.
  auto_post_sweep        — daily 9am: post a fresh take in the agent's voice
                            if its auto_post_schedule says daily/weekly.

Every Gemini call here routes through services.gemini.generate_for_agent so the
agent's persistent voice (bio + system_prompt + personality) is injected.
"""
from __future__ import annotations

import json
from collections import Counter
from datetime import datetime, timedelta

from app.core.db import SessionLocal
from app.core.logging import get_logger, log_event
from app.models import Agent, AgentAlert, AgentPost
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

# Heuristics — kept here, not config, because they're product decisions.
VIP_MIN_THREADS = 5             # contacts you've gotten >=5 messages from are "VIP"
URGENT_KEYWORDS = ("urgent", "asap", "today", "deadline")
POST_MAX_CHARS = 500            # mirror the agent_posts schema cap


# ── Helpers ────────────────────────────────────────────────────────────────
def _post(db, agent: Agent, content: str) -> AgentPost:
    """Drop a post on the agent's feed — same shape as POST /agents/{id}/post."""
    post = AgentPost(agent_id=agent.id, content=content[:POST_MAX_CHARS].strip())
    db.add(post)
    # Mirror the post into agent memory so it informs future voice — Layer 4 of
    # the memory pipeline (post_history).
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


# ── Morning briefing ────────────────────────────────────────────────────────
def morning_briefing_post():
    """8am daily — for every agent with the behavior enabled AND a connected
    integration, generate a one-paragraph briefing combining today's calendar
    and top-5 unread emails, then post it to the agent's feed."""

    def _do():
        db = SessionLocal()
        try:
            for agent in enabled_agents_for(db, JOB_MORNING_BRIEFING):
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
            for agent in enabled_agents_for(db, JOB_INBOX_MONITOR):
                user = agent.user
                if not user or not user.gmail_connected:
                    continue
                # Recent window — enough to derive VIPs AND surface fresh alerts.
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
                    # Dedupe via the unique (agent_id, message_id) constraint.
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

                # One feed post per sweep summarises everything new — never a
                # post per email, that would spam the feed.
                if len(alerted) == 1:
                    em = alerted[0]
                    tag = "VIP" if em["alert_type"] == "vip_email" else "Urgent"
                    instruction = (
                        f"In one short sentence as {user.name}'s agent, flag this "
                        f"newly-arrived {tag} email — what it is and who from. No "
                        f"preamble.\n\nEmail: from {em['sender']} <{em['sender_email']}>, "
                        f"subject '{em['subject']}'."
                    )
                else:
                    summary = "\n".join(
                        f"- {em['alert_type']}: '{em['subject']}' from {em['sender']}"
                        for em in alerted
                    )
                    instruction = (
                        f"In one short paragraph as {user.name}'s agent, flag these "
                        f"newly-arrived urgent/VIP emails. Keep it under 80 words.\n\n"
                        f"{summary}"
                    )
                text = (generate_for_agent(db, agent, instruction) or "").strip()
                if text:
                    _post(db, agent, text)
                    log_event(
                        logger, "inbox_monitor_posted",
                        agent_id=agent.id, alerts=len(alerted),
                    )
                mark_ran(db, agent.id, JOB_INBOX_MONITOR)
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
            today = datetime.utcnow()
            for agent in enabled_agents_for(db, JOB_AUTO_POST):
                if not auto_post_should_run_today(
                    agent.auto_post_schedule or "off", today
                ):
                    continue
                # Recent posts inform the voice but we don't want to retread them.
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
                    "your feed, in your own voice. The topic should reflect your "
                    "bio and your user's recent interests. Don't repeat anything "
                    "from your last posts. No hashtags, no quotes around the post.\n\n"
                    f"Your last posts:\n{recent_text}"
                )
                text = (generate_for_agent(db, agent, instruction) or "").strip()
                if not text:
                    continue
                _post(db, agent, text)
                mark_ran(db, agent.id, JOB_AUTO_POST)
                log_event(logger, "auto_post_posted", agent_id=agent.id)
        finally:
            db.close()

    _run("auto_post_sweep", _do)


def register_proactive_jobs(scheduler) -> None:
    """Wire the three proactive sweeps into APScheduler. Idempotent — every
    job is added with replace_existing so restart is safe."""
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
