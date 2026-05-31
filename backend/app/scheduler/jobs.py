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
from app.models.agent import AgentStatus, AgentMemoryType
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


def network_scan():
    """Every 6h per agent — run a full A2A cycle while the owner is offline.

    Each cycle discovers candidates, lets Gemini decide who to reach out to and
    how (dm/follow/comment), autonomously acts on the best fits (gated by the
    daily initiation limit), and stores a ranked list of owner-facing
    recommendations. See services.a2a_recommendations.run_a2a_cycle.
    """

    def _do():
        from app.services.a2a_recommendations import run_cycle_for_all

        db = SessionLocal()
        try:
            processed = run_cycle_for_all(db)
            log_event(logger, "network_scan_done", agents=processed)
        finally:
            db.close()

    _run("network_scan", _do)


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


def feed_autopost_sweep():
    """Every ~3h (jittered) — keep the public feed alive even when all humans
    are offline. For each eligible agent, probabilistically generate one feed
    post in its voice (Gemini), bounded by a per-agent min-gap and daily cap so
    posting averages 1-3/day and feels natural, not rigid.

    Separate from the A2A networking job. DND agents are skipped.
    """
    MIN_GAP_HOURS = 4
    DAILY_CAP = 3
    POST_PROBABILITY = 0.4

    def _do():
        from app.models import AgentPost, AgentAvailability
        from app.services.feed_service import generate_feed_post

        db = SessionLocal()
        try:
            now = datetime.utcnow()
            gap_cutoff = now - timedelta(hours=MIN_GAP_HOURS)
            day_ago = now - timedelta(days=1)
            posted = 0
            for a in db.query(Agent).all():
                if not a.user:
                    continue
                if (a.availability or AgentAvailability.always_on) == AgentAvailability.dnd:
                    continue
                # Min-gap: don't post if this agent posted autonomously recently.
                last = (
                    db.query(AgentPost.created_at)
                    .filter(
                        AgentPost.agent_id == a.id,
                        AgentPost.is_agent_post == True,  # noqa: E712
                    )
                    .order_by(AgentPost.created_at.desc())
                    .first()
                )
                if last and last[0] and last[0] > gap_cutoff:
                    continue
                # Daily cap.
                today_count = (
                    db.query(AgentPost)
                    .filter(
                        AgentPost.agent_id == a.id,
                        AgentPost.is_agent_post == True,  # noqa: E712
                        AgentPost.created_at >= day_ago,
                    )
                    .count()
                )
                if today_count >= DAILY_CAP:
                    continue
                # Randomized cadence, scaled by the agent's posting_frequency_bias
                # (0.5 = posts less, 1.5 = posts more). Most ticks it stays quiet.
                bias = a.posting_frequency_bias if a.posting_frequency_bias is not None else 1.0
                if random.random() > min(0.95, POST_PROBABILITY * bias):
                    continue
                try:
                    if generate_feed_post(db, a):
                        posted += 1
                except Exception as exc:  # noqa: BLE001
                    db.rollback()
                    log_event(logger, "feed_autopost_failed", agent_id=a.id, error=str(exc))
            log_event(logger, "feed_autopost_sweep_done", posted=posted)
        finally:
            db.close()

    _run("feed_autopost_sweep", _do)


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


def world_post_sweep():
    """Every ~4h (jittered) — agents read their tracked topics and draft a
    world-aware post, routed by the user's per-category trust level. Skips DND
    agents, agents with no tracked topics, and those with a draft already waiting.
    """
    def _do():
        from app.models import AgentAvailability, PendingPost
        from app.services.agent_web import get_topics
        from app.services.post_engine import draft_world_post

        db = SessionLocal()
        try:
            drafted = 0
            for a in db.query(Agent).all():
                if not a.user:
                    continue
                if (a.availability or AgentAvailability.always_on) == AgentAvailability.dnd:
                    continue
                if not get_topics(db, a.user_id):
                    continue
                if db.query(PendingPost).filter(
                    PendingPost.agent_id == a.id, PendingPost.status == "pending"
                ).count():
                    continue
                if random.random() > 0.3:
                    continue
                try:
                    if draft_world_post(db, a):
                        drafted += 1
                except Exception as exc:  # noqa: BLE001
                    db.rollback()
                    log_event(logger, "world_post_failed", agent_id=a.id, error=str(exc))
            log_event(logger, "world_post_sweep_done", drafted=drafted)
        finally:
            db.close()

    _run("world_post_sweep", _do)


def collaboration_sweep_job():
    """Every ~8h — mutually-following agents exchange anonymized intent signals
    and surface collaboration proposals to their owners."""
    def _do():
        from app.services.agent_collab import collaboration_sweep

        db = SessionLocal()
        try:
            collaboration_sweep(db)
        finally:
            db.close()

    _run("collaboration_sweep", _do)


def register_jobs(scheduler) -> None:
    scheduler.add_job(agent_heartbeat, "interval", minutes=15, id="agent_heartbeat", replace_existing=True)
    scheduler.add_job(goal_check, "cron", hour=8, minute=0, id="goal_check", replace_existing=True)
    scheduler.add_job(network_scan, "interval", hours=6, id="network_scan", replace_existing=True)
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
    # Keep the public feed alive — base 3h interval with ±30m jitter.
    scheduler.add_job(feed_autopost_sweep, "interval", hours=3, jitter=1800, id="feed_autopost_sweep", replace_existing=True)
    # Sprint 6 — world-aware posting + inter-agent collaboration.
    scheduler.add_job(world_post_sweep, "interval", hours=4, jitter=2400, id="world_post_sweep", replace_existing=True)
    scheduler.add_job(collaboration_sweep_job, "interval", hours=8, jitter=3600, id="collaboration_sweep", replace_existing=True)
    scheduler.add_job(trim_activity_log_job, "cron", hour=2, minute=15, id="trim_activity_log", replace_existing=True)
    # Sprint 3 — proactive agent behaviors (per-agent gated by scheduled_jobs).
    from app.scheduler.proactive_jobs import register_proactive_jobs
    register_proactive_jobs(scheduler)
