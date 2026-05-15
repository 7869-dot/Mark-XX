from datetime import datetime
from typing import Any, Optional
from app.schemas.base import ApiResponse, ApiMeta


def envelope(data: Any = None, agent_id: Optional[str] = None, error: Optional[str] = None) -> dict:
    return {
        "success": error is None,
        "data": data,
        "error": error,
        "meta": {"timestamp": datetime.utcnow().isoformat(), "agent_id": agent_id},
    }
