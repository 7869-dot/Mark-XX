"""APScheduler jobs for the Jarvis PA core.

Exactly five jobs survive the PA-core scope:
  agent_heartbeat   — keep agent status fresh (sleep idle agents).
  daily_briefing    — per-agent morning calendar briefing.
  classify_emails   — classify recent Gmail for connected users (email agent).
  inbox_monitor     — detect new replies in watched Gmail threads.
  opportunity_scan  — autonomous web-scout sweep (web agent), token-budgeted.

Every job is wrapped in a DB lock (job_lock) and uses the scheduler's
job_defaults (misfire_grace_time=300, coalesce=True, max_instances=1).
"""
from datetime import datetime, timedelta

from app.core.db import SessionLocal
from app.core.logging import get_logger, log_event
from app.models import Agent
from app.models.agent import AgentStatus
from app.scheduler.lock import job_lock

logger = get_logger("axolot.jobs")


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


# ---------------------------------------------------------------------------


def agent_heartbeat():
    def _do():
        db = SessionLocal()
        try:
            cutoff = datetime.utcnow() - timedelta(hours=24)
            for a in db.query(Agent).all():
                if (a.last_active_at or a.created_at) < cutoff and a.status != AgentStatus.sleeping:
                    a.status = AgentStatus.sleeping
                elif a.status == AgentStatus.busy and not a.current_task:
                    a.status = AgentStatus.idle
            db.commit()
        finally:
            db.close()

    _run("agent_heartbeat", _do)


def daily_briefing_job():
    """7:30am — per-agent morning calendar briefing."""

    def _do():
        from app.services.agent_calendar_tasks import daily_briefing

        db = SessionLocal()
        try:
            for a in db.query(Agent).all():
                if a.user and a.user.calendar_connected:
                    daily_briefing(db, a.id)
        finally:
            db.close()

    _run("daily_briefing", _do)


def classify_emails_job():
    """Every 30 min — classify recent Gmail messages for every connected user."""

    def _do():
        from app.services.email_classifier import classify_recent_for_user
        from app.models import User

        db = SessionLocal()
        try:
            for u in db.query(User).all():
                if not getattr(u, "gmail_connected", False):
                    continue
                try:
                    classify_recent_for_user(db, u)
                except Exception as exc:  # noqa: BLE001
                    log_event(
                        logger, "email_classify_failed",
                        user_id=u.id, error=str(exc),
                    )
        finally:
            db.close()

    _run("classify_emails", _do)


def inbox_monitor_job():
    """Every 2h — detect new replies in watched Gmail threads, queue a follow-up."""

    def _do():
        from app.models import WatchedThread, Task
        from app.models.task import TaskType, TaskStatus, TaskTrigger
        from app.services import gmail_service

        db = SessionLocal()
        try:
            for wt in db.query(WatchedThread).filter(
                WatchedThread.is_active == True  # noqa: E712
            ).all():
                latest = gmail_service.latest_message_id(db, wt.user_id, wt.thread_id)
                wt.last_checked_at = datetime.utcnow()
                if latest and latest != wt.last_message_id:
                    db.add(Task(
                        agent_id=wt.agent_id, user_id=wt.user_id,
                        title=f"New reply: {wt.subject[:60]}",
                        description=f"A new message arrived in the thread '{wt.subject}'.",
                        task_type=TaskType.monitoring,
                        status=TaskStatus.awaiting_human, priority=3,
                        requires_human_approval=True,
                        triggered_by=TaskTrigger.scheduled,
                        result={"summary": f"New reply in '{wt.subject}'",
                                "thread_id": wt.thread_id},
                    ))
                    wt.last_message_id = latest
                    log_event(logger, "watched_thread_new_reply",
                              thread_id=wt.thread_id, user_id=wt.user_id)
                db.commit()
        finally:
            db.close()

    _run("inbox_monitor", _do)


def opportunity_scan_job():
    """Autonomous web-scout sweep — finds opportunities for onboarded users while
    they're offline. Token-budgeted: skips any user scanned within the cooldown
    window and stops after MAX_USERS_PER_RUN scans per sweep. The scout itself
    dedupes finds by URL and ranks by relevance, so nothing identical is
    re-summarised. Disabled entirely via OPPORTUNITY_SCAN_ENABLED."""

    def _do():
        from app.core.config import settings
        from app.models import User, UserProfile
        from app.models.jarvis_profile import AgentRunLog
        from app.services import web_agent
        from app.services.agent_runs import WEB_AGENT

        if not settings.OPPORTUNITY_SCAN_ENABLED:
            return
        cooldown = timedelta(hours=settings.OPPORTUNITY_SCAN_COOLDOWN_HOURS)
        budget = max(1, settings.OPPORTUNITY_SCAN_MAX_USERS_PER_RUN)

        db = SessionLocal()
        scanned = 0
        try:
            # Only onboarded users have interests/goals worth scanning against.
            onboarded = (
                db.query(User)
                .join(UserProfile, UserProfile.user_id == User.id)
                .filter(UserProfile.onboarding_complete.is_(True))
                .all()
            )
            for user in onboarded:
                if scanned >= budget:
                    log_event(logger, "opportunity_scan_budget_hit", budget=budget)
                    break
                # Cooldown: skip users whose scout ran within the window.
                last = (
                    db.query(AgentRunLog)
                    .filter(AgentRunLog.user_id == user.id, AgentRunLog.agent_name == WEB_AGENT)
                    .order_by(AgentRunLog.ran_at.desc())
                    .first()
                )
                if last and last.ran_at and (datetime.utcnow() - last.ran_at) < cooldown:
                    continue
                try:
                    web_agent.run_report(db, user)
                    scanned += 1
                except Exception as exc:  # noqa: BLE001
                    log_event(logger, "opportunity_scan_user_failed", user_id=user.id, error=str(exc))
            log_event(logger, "opportunity_scan_done", scanned=scanned, eligible=len(onboarded))
        finally:
            db.close()

    _run("opportunity_scan", _do)


def register_jobs(scheduler) -> None:
    scheduler.add_job(agent_heartbeat, "interval", minutes=15, id="agent_heartbeat", replace_existing=True)
    scheduler.add_job(daily_briefing_job, "cron", hour=7, minute=30, id="daily_briefing", replace_existing=True)
    scheduler.add_job(classify_emails_job, "interval", minutes=30, id="classify_emails", replace_existing=True)
    scheduler.add_job(inbox_monitor_job, "interval", hours=2, id="inbox_monitor", replace_existing=True)
    # Autonomous opportunity scan — every 3h, token-budgeted (see config caps).
    scheduler.add_job(opportunity_scan_job, "interval", hours=3, id="opportunity_scan", replace_existing=True)
