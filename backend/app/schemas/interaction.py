from datetime import datetime
from typing import Optional
from pydantic import BaseModel
from app.schemas.base import ORMModel


class InteractionCreate(BaseModel):
    target_agent_id: str
    interaction_type: str = "introduction"
    message: Optional[str] = None       # if None, agent will generate
    custom_message: Optional[str] = None  # spec alias for message


class InteractionOut(ORMModel):
    id: str
    initiator_agent_id: str
    target_agent_id: str
    interaction_type: str
    message: str
    response: Optional[str]
    status: str
    compatibility_score: float
    created_at: datetime
    responded_at: Optional[datetime]
