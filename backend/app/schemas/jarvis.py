"""Jarvis wake-up contract — the shapes the home screen consumes."""
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AgentTask(BaseModel):
    # Jarvis never assigns to the posting agent (public voice stays user-driven).
    agent_role: Literal["email", "wildcard"]
    task_description: str
    priority: Literal["now", "today", "this_week"] = "today"
    status: Literal["pending", "in_progress", "done"] = "pending"


class JarvisContext(BaseModel):
    greeting: str
    question: str
    known_about_user: list[str] = Field(default_factory=list)
    team_briefing: list[AgentTask] = Field(default_factory=list)
    timestamp: datetime = Field(default_factory=datetime.utcnow)


class AgentTaskResult(BaseModel):
    task_id: str
    agent_role: str
    draft_content: str
    subject_line: str
    recipient_hint: str
    requires_approval: bool = True
    created_at: datetime
