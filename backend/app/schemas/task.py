from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel
from app.schemas.base import ORMModel


class TaskCreate(BaseModel):
    title: str
    description: str
    task_type: str = "research"
    priority: int = 3
    requires_human_approval: bool = False


class TaskOut(ORMModel):
    id: str
    agent_id: str
    user_id: str
    title: str
    description: str
    task_type: str
    status: str
    priority: int
    result: Optional[Any]
    requires_human_approval: bool
    triggered_by: str
    rejection_feedback: Optional[str]
    created_at: datetime
    started_at: Optional[datetime]
    completed_at: Optional[datetime]


class TaskReject(BaseModel):
    feedback: Optional[str] = None
