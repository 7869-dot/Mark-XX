"""Unified activity feed combining tasks, interactions, and memories."""
from datetime import datetime
from sqlalchemy.orm import Session
from sqlalchemy import or_

from app.models import Task, AgentInteraction, AgentMemory, Agent


def build_feed(db: Session, agent: Agent, limit: int = 30, offset: int = 0) -> list[dict]:
    items: list[dict] = []

    tasks = (
        db.query(Task)
        .filter(Task.agent_id == agent.id)
        .order_by(Task.created_at.desc())
        .limit(limit)
        .all()
    )
    for t in tasks:
        kind = "awaiting_approval" if t.status.value == "awaiting_human" else "task"
        items.append({
            "id": f"task-{t.id}",
            "kind": kind,
            "ref_id": t.id,
            "title": _task_title(t),
            "description": (t.result or {}).get("summary") if t.result else t.description[:160],
            "status": t.status.value,
            "task_type": t.task_type.value,
            "timestamp": t.created_at.isoformat(),
        })

    interactions = (
        db.query(AgentInteraction)
        .filter(or_(
            AgentInteraction.initiator_agent_id == agent.id,
            AgentInteraction.target_agent_id == agent.id,
        ))
        .order_by(AgentInteraction.created_at.desc())
        .limit(limit)
        .all()
    )
    for i in interactions:
        outbound = i.initiator_agent_id == agent.id
        other_id = i.target_agent_id if outbound else i.initiator_agent_id
        other = db.query(Agent).filter(Agent.id == other_id).first()
        other_name = other.name if other else "another agent"
        items.append({
            "id": f"interaction-{i.id}",
            "kind": "interaction",
            "ref_id": i.id,
            "title": (
                f"Your agent reached out to {other_name}"
                if outbound else f"{other_name} reached out to your agent"
            ),
            "description": i.message[:200],
            "compatibility_score": i.compatibility_score,
            "outbound": outbound,
            "other_agent_id": other_id,
            "timestamp": i.created_at.isoformat(),
        })

    memories = (
        db.query(AgentMemory)
        .filter(AgentMemory.agent_id == agent.id, AgentMemory.memory_type == "milestone")
        .order_by(AgentMemory.created_at.desc())
        .limit(5)
        .all()
    )
    for m in memories:
        items.append({
            "id": f"memory-{m.id}",
            "kind": "memory",
            "ref_id": m.id,
            "title": "Memory captured",
            "description": m.content,
            "importance": m.importance_score,
            "timestamp": m.created_at.isoformat(),
        })

    items.sort(key=lambda x: x["timestamp"], reverse=True)
    return items[offset: offset + limit]


def _task_title(t: Task) -> str:
    if t.status.value == "awaiting_human":
        return f"Your agent needs your approval: {t.title}"
    if t.status.value == "completed":
        return f"Your agent completed: {t.title}"
    if t.status.value == "running":
        return f"Your agent is working on: {t.title}"
    if t.status.value == "failed":
        return f"Task failed: {t.title}"
    return f"Task queued: {t.title}"
