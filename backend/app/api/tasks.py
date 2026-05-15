from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks, Request
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import get_current_user
from app.core.ratelimit import limiter
from app.models import User, Task
from app.models.task import TaskStatus, TaskType, TaskTrigger
from app.api.envelope import envelope
from app.schemas.task import TaskCreate, TaskReject
from app.services.task_engine import execute_task
from app.services.agent_service import add_memory
from app.services.reputation import record_event
from app.models.agent import AgentMemoryType


router = APIRouter(prefix="/tasks", tags=["tasks"])


def _task_dict(t: Task) -> dict:
    return {
        "id": t.id,
        "agent_id": t.agent_id,
        "user_id": t.user_id,
        "title": t.title,
        "description": t.description,
        "task_type": t.task_type.value if hasattr(t.task_type, "value") else t.task_type,
        "status": t.status.value if hasattr(t.status, "value") else t.status,
        "priority": t.priority,
        "result": t.result,
        "requires_human_approval": t.requires_human_approval,
        "triggered_by": t.triggered_by.value if hasattr(t.triggered_by, "value") else t.triggered_by,
        "rejection_feedback": t.rejection_feedback,
        "created_at": t.created_at.isoformat(),
        "started_at": t.started_at.isoformat() if t.started_at else None,
        "completed_at": t.completed_at.isoformat() if t.completed_at else None,
    }


@router.post("/create")
@limiter.limit("10/minute")
def create_task(
    request: Request,
    payload: TaskCreate,
    background: BackgroundTasks,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    if not user.agent:
        raise HTTPException(status_code=404, detail="No agent")
    try:
        task_type = TaskType(payload.task_type)
    except ValueError:
        task_type = TaskType.research
    task = Task(
        agent_id=user.agent.id,
        user_id=user.id,
        title=payload.title,
        description=payload.description,
        task_type=task_type,
        priority=max(1, min(5, payload.priority)),
        requires_human_approval=payload.requires_human_approval,
        triggered_by=TaskTrigger.user,
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    background.add_task(execute_task, task.id)
    return envelope(_task_dict(task), agent_id=user.agent.id)


@router.get("/my")
def my_tasks(
    status: str | None = None,
    limit: int = 50,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    q = db.query(Task).filter(Task.user_id == user.id)
    if status:
        q = q.filter(Task.status == status)
    items = q.order_by(Task.created_at.desc()).limit(limit).all()
    return envelope([_task_dict(t) for t in items], agent_id=user.agent.id if user.agent else None)


@router.get("/pending")
def pending(db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    items = (
        db.query(Task)
        .filter(Task.user_id == user.id, Task.status == TaskStatus.awaiting_human)
        .order_by(Task.created_at.desc())
        .all()
    )
    return envelope([_task_dict(t) for t in items], agent_id=user.agent.id if user.agent else None)


@router.get("/{task_id}")
def get_task(task_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    return envelope(_task_dict(t), agent_id=user.agent.id if user.agent else None)


@router.post("/{task_id}/approve")
def approve(task_id: str, db: Session = Depends(get_db), user: User = Depends(get_current_user)):
    t = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    if t.status != TaskStatus.awaiting_human:
        raise HTTPException(status_code=400, detail="Task is not awaiting approval")
    t.status = TaskStatus.completed
    t.completed_at = datetime.utcnow()
    agent = user.agent
    agent.total_tasks_completed = (agent.total_tasks_completed or 0) + 1
    record_event(db, agent, "task_approved", reason=f"approved task {t.id}")
    add_memory(
        db, agent, AgentMemoryType.task_outcome,
        f"User approved task: {t.title}",
        importance=0.7,
    )
    db.commit()
    return envelope(_task_dict(t), agent_id=agent.id)


@router.post("/{task_id}/reject")
def reject(
    task_id: str,
    payload: TaskReject,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    t = db.query(Task).filter(Task.id == task_id, Task.user_id == user.id).first()
    if not t:
        raise HTTPException(status_code=404, detail="Task not found")
    if t.status != TaskStatus.awaiting_human:
        raise HTTPException(status_code=400, detail="Task is not awaiting approval")
    t.status = TaskStatus.rejected
    t.rejection_feedback = payload.feedback
    t.completed_at = datetime.utcnow()
    agent = user.agent
    record_event(db, agent, "task_rejected", reason=f"rejected task {t.id}")
    add_memory(
        db, agent, AgentMemoryType.learned_preference,
        f"User rejected task '{t.title}'. Feedback: {payload.feedback or 'none'}",
        importance=0.8,
    )
    db.commit()
    return envelope(_task_dict(t), agent_id=agent.id)
