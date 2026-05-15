from datetime import datetime
from typing import Optional, Any
from pydantic import BaseModel
from app.schemas.base import ORMModel


class PersonalityVector(BaseModel):
    openness: float = 0.5
    directness: float = 0.5
    ambition: float = 0.5
    sociability: float = 0.5
    risk_tolerance: float = 0.5


class AgentOut(ORMModel):
    id: str
    user_id: str
    name: str
    personality_vector: dict
    reputation_score: float
    social_graph: list
    status: str
    current_task: Optional[str]
    total_tasks_completed: int
    avatar_seed: str
    created_at: datetime
    last_active_at: datetime


class AgentUpdate(BaseModel):
    name: Optional[str] = None
    goals: Optional[list[str]] = None


class AgentPublicProfile(BaseModel):
    id: str
    name: str
    user_name: str
    reputation_score: float
    personality_vector: dict
    total_tasks_completed: int
    status: str
    avatar_seed: str
    interests: list = []


class AgentStats(BaseModel):
    tasks_today: int
    tasks_week: int
    tasks_total: int
    connections: int
    interactions_today: int
    time_saved_minutes: int
    reputation_score: float
