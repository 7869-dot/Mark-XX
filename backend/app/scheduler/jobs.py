"""APScheduler jobs that make agents feel alive.

Every job is wrapped in a DB lock (job_lock) and uses the scheduler's
job_defaults (misfire_grace_time=300, coalesce=True, max_instances=1).
"""
import json
import random
from datetime import datetime, timedelta

from app.core.db import SessionLocal
from app.core.logging import get_logger, log_event
from app.models import Agent, Task, AgentInteraction, ChatHistory, UserPersonality, AgentMemory
from app.models.agent import AgentStatus, AgentMemoryType, AgentRole
from app.models.task import TaskType, TaskStatus, TaskTrigger
from app.prompts.templates import DAILY_DIGEST, PERSONALITY_DERIVATION, GOAL_TASKS
from app.services.gemini import generate
from app.services.a2a import discover_compatible, initiate_interaction, can_initiate
from app.services.agent_service import add_memory
from app.services.reputation import decay_toward_baseline
from app.services.context_builder import build_agent_context
from app.services.task_engine import execute_task, reap_stuck_tasks
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
        reap_stuck_tasks()  # also fail any task past its timeout

    _run("agent_heartbeat", _do)


def goal_check():
    """Daily 8am — Gemini-driven, goal-specific task proposals (exactly 3)."""

    def _do():
        db = SessionLocal()
        try:
            for a in db.query(Agent).all():
                goals = (a.user.goals if a.user else []) or []
                if not goals:
                    continue
                open_count = db.query(Task).filter(
                    Task.agent_id == a.id,
                    Task.status.in_([TaskStatus.queued, TaskStatus.running, TaskStatus.awaiting_human]),
                ).count()
                if open_count >= 5:
                    continue

                ctx = build_agent_context(db, a)
                prompt = GOAL_TASKS.format(
                    agent_name=a.name,
                    user_name=a.user.name if a.user else "User",
                    goals="\n".join(f"- {g}" for g in goals),
                    personality_summary=ctx["personality_summary"],
                )
                raw = generate(prompt, response_format="goal_tasks")
                try:
                    proposed = json.loads(raw)
                except (json.JSONDecodeError, TypeError):
                    continue
                if not isinstance(proposed, list):
                    continue

                created_ids: list[str] = []
                for p in proposed[:3]:
                    try:
                        ttype = TaskType(p.get("task_type", "research"))
                    except ValueError:
                        ttype = TaskType.research
                    requires_approval = bool(p.get("requires_human_approval", False))
                    task = Task(
                        agent_id=a.id,
                        user_id=a.user_id,
                        title=str(p.get("title", "Advance a goal"))[:120],
                        description=str(p.get("description", "")),
                        task_type=ttype,
                        priority=max(1, min(5, int(p.get("priority", 3)))),
                        requires_human_approval=requires_approval,
                        triggered_by=TaskTrigger.agent_self,
                        status=TaskStatus.queued,
                    )
                    db.add(task)
                    db.commit()
                    db.refresh(task)
                    # Approval-required tasks wait in the inbox; others run now.
                    if not requires_approval:
                        created_ids.append(task.id)
                for tid in created_ids:
                    execute_task(tid)
        finally:
            db.close()

    _run("goal_check", _do)


def task_digest():
    """Daily 7pm — structured digest stored as a digest feed item (milestone memory)."""
    TIME_SAVED = {
        "research": 45, "outreach": 30, "scheduling": 20, "analysis": 60,
        "networking": 40, "negotiation": 90, "monitoring": 15,
    }

    def _do():
        db = SessionLocal()
        try:
            day_ago = datetime.utcnow() - timedelta(days=1)
            for a in db.query(Agent).all():
                done = db.query(Task).filter(
                    Task.agent_id == a.id,
                    Task.status == TaskStatus.completed,
                    Task.completed_at >= day_ago,
                ).all()
                new_conns = db.query(AgentInteraction).filter(
                    AgentInteraction.initiator_agent_id == a.id,
                    AgentInteraction.status == "accepted",
                    AgentInteraction.created_at >= day_ago,
                ).count()
                queued = db.query(Task).filter(
                    Task.agent_id == a.id, Task.status == TaskStatus.queued
                ).count()
                if not done and not new_conns and not queued:
                    continue

                minutes = sum(
                    TIME_SAVED.get(
                        t.task_type.value if hasattr(t.task_type, "value") else t.task_type, 20
                    )
                    for t in done
                )
                hours = round(minutes / 60, 1)
                top3 = "; ".join(
                    (t.result or {}).get("summary", t.title) for t in done[:3]
                ) or "steady background work"
                digest = (
                    f"Today, your agent completed {len(done)} tasks, saved you approximately "
                    f"{hours} hours, and made {new_conns} new connections. "
                    f"Highlights: {top3}. Tomorrow, it has {queued} tasks queued."
                )
                m = AgentMemory(
                    agent_id=a.id,
                    memory_type=AgentMemoryType.milestone,
                    content=digest,
                    importance_score=0.75,
                )
                # tag so the feed can render it as feed_item_type="digest"
                m.content = "[digest] " + digest
                db.add(m)
                db.commit()
        finally:
            db.close()

    _run("task_digest", _do)


def personality_update():
    """Weekly — re-derive personality_vector, soft-blended to avoid whiplash."""

    def _do():
        db = SessionLocal()
        try:
            for a in db.query(Agent).all():
                chats = (
                    db.query(ChatHistory)
                    .filter(ChatHistory.user_id == a.user_id)
                    .order_by(ChatHistory.created_at.desc())
                    .limit(20)
                    .all()
                )
                personality = db.query(UserPersonality).filter(
                    UserPersonality.user_id == a.user_id
                ).first()
                if not chats and not personality:
                    continue
                prompt = PERSONALITY_DERIVATION.format(
                    recent_chats="\n".join(f"[{c.role}] {c.content}" for c in reversed(chats)) or "—",
                    personality_notes=(personality.notes if personality else "—") or "—",
                )
                raw = generate(prompt, response_format="personality")
                try:
                    vec = json.loads(raw)
                    current = a.personality_vector or {}
                    a.personality_vector = {
                        k: round(current.get(k, 0.5) * 0.6 + float(vec.get(k, 0.5)) * 0.4, 3)
                        for k in ["openness", "directness", "ambition", "sociability", "risk_tolerance"]
                    }
                    db.commit()
                except (json.JSONDecodeError, ValueError, TypeError):
                    continue
        finally:
            db.close()

    _run("personality_update", _do)


def reputation_decay():
    """Weekly — decay inactive agents toward baseline via a recorded event."""

    def _do():
        db = SessionLocal()
        try:
            cutoff = datetime.utcnow() - timedelta(days=7)
            for a in db.query(Agent).all():
                if (a.last_active_at or a.created_at) < cutoff:
                    decay_toward_baseline(db, a, rate=0.05)
        finally:
            db.close()

    _run("reputation_decay", _do)


def memory_mining():
    """Daily 3am — mine 30d of chat/task history into tags, goals, personality."""

    def _do():
        from app.services.memory_indexer import run_memory_mining

        db = SessionLocal()
        try:
            run_memory_mining(db)
        finally:
            db.close()

    _run("memory_mining", _do)


def check_watched_threads():
    """Every 2h — detect new replies in watched Gmail threads, notify the human."""

    def _do():
        from app.models import WatchedThread
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

    _run("check_watched_threads", _do)


def weekly_email_digest_job():
    """Mondays 8am — per-agent weekly email digest task."""

    def _do():
        from app.services.agent_email_tasks import weekly_email_digest

        db = SessionLocal()
        try:
            for a in db.query(Agent).all():
                if a.user and a.user.gmail_connected:
                    weekly_email_digest(db, a.id)
        finally:
            db.close()

    _run("weekly_email_digest", _do)


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


def prep_for_meeting_sweep():
    """Every 15m — surface a prep note ~30 min before each upcoming meeting."""

    def _do():
        from app.services import calendar_service
        from app.services.agent_calendar_tasks import prep_for_meeting
        from app.models import Task

        db = SessionLocal()
        try:
            now = datetime.utcnow()
            for a in db.query(Agent).all():
                if not (a.user and a.user.calendar_connected):
                    continue
                for ev in calendar_service.list_events(db, a.user_id, days_ahead=1):
                    try:
                        start = datetime.fromisoformat(
                            str(ev["start"]).replace("Z", "")
                        )
                    except (ValueError, TypeError):
                        continue
                    mins = (start - now).total_seconds() / 60
                    if 15 <= mins <= 35:
                        already = db.query(Task).filter(
                            Task.agent_id == a.id,
                            Task.title == f"Prep: {ev['summary'][:50]}",
                        ).first()
                        if not already:
                            prep_for_meeting(db, a.id, ev["id"])
        finally:
            db.close()

    _run("prep_for_meeting_sweep", _do)


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


def process_a2a_inbox_job():
    """Every 5 min — process unread A2A messages and generate auto-replies."""

    def _do():
        from app.services.a2a_async import process_all_unread

        db = SessionLocal()
        try:
            replied = process_all_unread(db)
            log_event(logger, "a2a_processed", replied=replied)
        finally:
            db.close()

    _run("process_a2a_inbox", _do)


def trim_activity_log_job():
    """Daily — keep agent_activity_log bounded so the table doesn't grow forever."""

    def _do():
        from app.services.activity_logger import trim_old_activity

        db = SessionLocal()
        try:
            n = trim_old_activity(db, retain_days=30)
            log_event(logger, "activity_log_trimmed", removed=n)
        finally:
            db.close()

    _run("trim_activity_log", _do)


def register_jobs(scheduler) -> None:
    scheduler.add_job(agent_heartbeat, "interval", minutes=15, id="agent_heartbeat", replace_existing=True)
    scheduler.add_job(goal_check, "cron", hour=8, minute=0, id="goal_check", replace_existing=True)
    scheduler.add_job(task_digest, "cron", hour=19, minute=0, id="task_digest", replace_existing=True)
    scheduler.add_job(personality_update, "cron", day_of_week="sun", hour=3, id="personality_update", replace_existing=True)
    scheduler.add_job(reputation_decay, "cron", day_of_week="sun", hour=4, id="reputation_decay", replace_existing=True)
    scheduler.add_job(memory_mining, "cron", hour=3, minute=0, id="memory_mining", replace_existing=True)
    scheduler.add_job(check_watched_threads, "interval", hours=2, id="check_watched_threads", replace_existing=True)
    scheduler.add_job(weekly_email_digest_job, "cron", day_of_week="mon", hour=8, minute=0, id="weekly_email_digest", replace_existing=True)
    scheduler.add_job(daily_briefing_job, "cron", hour=7, minute=30, id="daily_briefing", replace_existing=True)
    scheduler.add_job(prep_for_meeting_sweep, "interval", minutes=15, id="prep_for_meeting_sweep", replace_existing=True)
    scheduler.add_job(classify_emails_job, "interval", minutes=30, id="classify_emails", replace_existing=True)
    scheduler.add_job(process_a2a_inbox_job, "interval", minutes=5, id="process_a2a_inbox", replace_existing=True)
    scheduler.add_job(trim_activity_log_job, "cron", hour=2, minute=15, id="trim_activity_log", replace_existing=True)
    # Autonomous opportunity scan — every 3h, token-budgeted (see config caps).
    scheduler.add_job(opportunity_scan_job, "interval", hours=3, id="opportunity_scan", replace_existing=True)
    # Proactive agent behaviors (per-agent gated by scheduled_jobs).
    from app.scheduler.proactive_jobs import register_proactive_jobs
    register_proactive_jobs(scheduler)
