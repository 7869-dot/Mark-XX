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
    """Every 6h per agent — discover top-5 candidates, auto-introduce to #1 (score>60).

    Rules: exclude already-connected, exclude discovered in last 7d, exclude same
    user. Max 1 auto-introduction per agent per day. Log all 5 to discovery log.
    """

    def _do():
        from app.services.compatibility import compute_compatibility
        from app.services.a2a_engine import (
            already_connected,
            recently_discovered,
            log_discovery,
            run_interaction,
        )

        db = SessionLocal()
        try:
            day_ago = datetime.utcnow() - timedelta(days=1)
            for a in db.query(Agent).all():
                if not a.user:
                    continue

                # Max 1 auto-introduction per agent per day.
                if db.query(AgentInteraction).filter(
                    AgentInteraction.initiator_agent_id == a.id,
                    AgentInteraction.created_at >= day_ago,
                ).count() >= 1:
                    continue

                candidates = []
                for other in db.query(Agent).filter(Agent.id != a.id).all():
                    if other.user_id == a.user_id:
                        continue
                    if already_connected(db, a.id, other.id):
                        continue
                    if recently_discovered(db, a.id, other.id, days=7):
                        continue
                    compat = compute_compatibility(a, other)
                    candidates.append((other, compat))

                if not candidates:
                    continue
                candidates.sort(key=lambda x: x[1]["score"], reverse=True)
                top5 = candidates[:5]

                # Log all 5 for future reference.
                for other, compat in top5:
                    log_discovery(
                        db, a.id, other.id, compat["score"], compat["reason"],
                        acted_on=False, commit=False,
                    )
                db.commit()

                # Auto-introduce to #1 only if score > 60.
                best, best_compat = top5[0]
                if best_compat["score"] > 60:
                    interaction, _ = run_interaction(db, a, best)
                    add_memory(
                        db, a, AgentMemoryType.interaction,
                        f"Reached out to {best.name} — {best_compat['reason']} "
                        f"(compat {best_compat['score']:.0f}).",
                        importance=0.6,
                    )
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


def register_jobs(scheduler) -> None:
    scheduler.add_job(agent_heartbeat, "interval", minutes=15, id="agent_heartbeat", replace_existing=True)
    scheduler.add_job(goal_check, "cron", hour=8, minute=0, id="goal_check", replace_existing=True)
    scheduler.add_job(network_scan, "interval", hours=6, id="network_scan", replace_existing=True)
    scheduler.add_job(task_digest, "cron", hour=19, minute=0, id="task_digest", replace_existing=True)
    scheduler.add_job(personality_update, "cron", day_of_week="sun", hour=3, id="personality_update", replace_existing=True)
    scheduler.add_job(reputation_decay, "cron", day_of_week="sun", hour=4, id="reputation_decay", replace_existing=True)
    scheduler.add_job(memory_mining, "cron", hour=3, minute=0, id="memory_mining", replace_existing=True)
