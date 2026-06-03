"""Jarvis wake-up + chat contract — the shapes the home screen + chat consume."""
import enum
from datetime import datetime
from typing import Literal

from pydantic import BaseModel, Field


class AgentTask(BaseModel):
    # Jarvis never assigns to the feed agent (public voice stays user-driven).
    agent_role: Literal["email", "web"]
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


# ── Chat command modes (Sprint 3A) ───────────────────────────────────────────
class ChatMode(str, enum.Enum):
    AUTO = "auto"           # Jarvis classifies the task and delegates to a sub-agent
    DEFAULT = "default"     # open Jarvis conversation
    EMAIL = "email"         # routes to email agent
    SCHEDULE = "schedule"   # routes to scheduler agent
    RESEARCH = "research"   # web search + synthesis (web agent)
    POST = "post"           # draft for the posting agent to queue


class JarvisAction(BaseModel):
    type: Literal["draft_email", "schedule_event", "research_result", "post_draft"]
    payload: dict
    requires_approval: bool = True


class JarvisChatRequest(BaseModel):
    message: str = Field(..., min_length=1, max_length=4000)
    mode: ChatMode = ChatMode.DEFAULT
    context: dict | None = None


class JarvisChatResponse(BaseModel):
    reply: str
    mode: ChatMode
    action: JarvisAction | None = None
    follow_up: str | None = None
    # When the user sends mode=AUTO, this is the sub-agent Jarvis delegated to
    # (email | web | schedule | post | self). Lets the UI show the routing.
    delegated_to: str | None = None
    # Durable interests Jarvis captured from this message and saved to memory.
    # Empty for most turns; lets the UI confirm "I'll keep an eye out for X".
    remembered_interests: list[str] = []
