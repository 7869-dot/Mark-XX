"""Task execution: runs queued tasks through Gemini and stores results."""
import json
from datetime import datetime, timedelta
from sqlalchemy.orm import Session

from app.core.db import SessionLocal
from app.core.logging import get_logger, log_event
from app.models import Task, Agent
from app.models.task import TaskStatus
from app.models.agent import AgentStatus, AgentMemoryType
from app.prompts.templates import TASK_EXECUTION
from app.services.gemini import generate
from app.services.context_builder import build_agent_context
from app.services.agent_service import set_status, add_memory
from app.services.reputation import record_event

logger = get_logger("axolot.task_engine")


def execute_task(task_id: str) -> None:
    """Run a queued task. Called via FastAPI BackgroundTasks / scheduler.

    Guarantees the task never hangs in "running": Gemini always returns a
    string (it degrades to a stub on failure), and any exception transitions
    the task to failed with a reason.
    """
    db = SessionLocal()
    task = None
    try:
        task = db.query(Task).filter(Task.id == task_id).first()
        if not task or task.status != TaskStatus.queued:
            return
        agent = db.query(Agent).filter(Agent.id == task.agent_id).first()
        if not agent:
            return

        task.status = TaskStatus.running
        task.started_at = datetime.utcnow()
        set_status(db, agent, AgentStatus.busy, current_task=task.title)
        db.commit()
        log_event(logger, "task_transition", task_id=task.id, to="running")

        _tt = task.task_type.value if hasattr(task.task_type, "value") else task.task_type
        ctx = build_agent_context(db, agent, task_type=_tt)
        prompt = TASK_EXECUTION.format(
            task_type=_tt,
            task_title=task.title,
            task_description=task.description,
            **ctx,
        )
        raw = generate(prompt, response_format="task")
        try:
            payload = json.loads(raw)
        except (json.JSONDecodeError, TypeError):
            payload = {
                "summary": (raw or "")[:200],
                "result": raw,
                "recommended_action": None,
                "requires_human_approval": task.requires_human_approval,
                "approval_reason": None,
            }

        task.result = payload
        if task.requires_human_approval or payload.get("requires_human_approval"):
            task.status = TaskStatus.awaiting_human
            log_event(logger, "task_transition", task_id=task.id, to="awaiting_human")
        else:
            task.status = TaskStatus.completed
            task.completed_at = datetime.utcnow()
            agent.total_tasks_completed = (agent.total_tasks_completed or 0) + 1
            record_event(db, agent, "task_completed", reason=f"task {task.id}")
            add_memory(
                db,
                agent,
                AgentMemoryType.task_outcome,
                f"Completed task: {task.title}. {payload.get('summary', '')}",
                importance=0.5,
            )
            log_event(logger, "task_transition", task_id=task.id, to="completed")

        set_status(db, agent, AgentStatus.idle, current_task=None)
        db.commit()
    except Exception as exc:  # noqa: BLE001
        db.rollback()
        if task is not None:
            task.status = TaskStatus.failed
            task.result = {"error": str(exc), "reason": "execution_exception"}
            task.completed_at = datetime.utcnow()
            db.commit()
        log_event(logger, "task_failed", task_id=task_id, error=str(exc))
    finally:
        db.close()


def reap_stuck_tasks() -> int:
    """Fail any task that has been 'running' past its timeout. Returns count reaped."""
    db = SessionLocal()
    reaped = 0
    try:
        running = db.query(Task).filter(Task.status == TaskStatus.running).all()
        now = datetime.utcnow()
        for t in running:
            timeout = t.task_timeout_minutes or 10
            started = t.started_at or t.created_at
            if started and now - started > timedelta(minutes=timeout):
                t.status = TaskStatus.failed
                t.result = {"error": "timeout", "reason": f"exceeded {timeout}m"}
                t.completed_at = now
                agent = db.query(Agent).filter(Agent.id == t.agent_id).first()
                if agent and agent.status == AgentStatus.busy:
                    agent.status = AgentStatus.idle
                    agent.current_task = None
                reaped += 1
                log_event(logger, "task_reaped", task_id=t.id, timeout_min=timeout)
        if reaped:
            db.commit()
    finally:
        db.close()
    return reaped
