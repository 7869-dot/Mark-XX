from datetime import datetime
from typing import Any, Generic, Optional, TypeVar
from pydantic import BaseModel, ConfigDict


T = TypeVar("T")


class ApiMeta(BaseModel):
    timestamp: datetime
    agent_id: Optional[str] = None


class ApiResponse(BaseModel, Generic[T]):
    success: bool = True
    data: Optional[T] = None
    error: Optional[str] = None
    meta: ApiMeta


class ORMModel(BaseModel):
    model_config = ConfigDict(from_attributes=True)
