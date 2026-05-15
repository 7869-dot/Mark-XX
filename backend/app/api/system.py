from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from sqlalchemy import func, text

from app.core.db import get_db
from app.core.cache import cache
from app.models import Agent, Task, AgentInteraction
from app.api.envelope import envelope
from app.services.gemini import ping as gemini_ping


router = APIRouter(tags=["system"])


@router.get("/health")
def health(response: Response, db: Session = Depends(get_db)):
    """Railway deploy health check — 200 only if DB, scheduler, and Gemini pass."""
    checks = {"database": False, "scheduler": False, "gemini": False}

    try:
        db.execute(text("SELECT 1"))
        checks["database"] = True
    except Exception:  # noqa: BLE001
        pass

    try:
        from app.main import scheduler  # late import to avoid cycle

        checks["scheduler"] = bool(scheduler.running)
    except Exception:  # noqa: BLE001
        pass

    try:
        checks["gemini"] = gemini_ping()
    except Exception:  # noqa: BLE001
        pass

    ok = all(checks.values())
    if not ok:
        response.status_code = 503
    return envelope({
        "status": "ok" if ok else "degraded",
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat(),
    })


@router.get("/platform/stats")
def platform_stats(db: Session = Depends(get_db)):
    cached = cache.get("platform_stats")
    if cached is not None:
        return envelope(cached)
    day_ago = datetime.utcnow() - timedelta(days=1)
    data = {
        "total_agents": db.query(func.count(Agent.id)).scalar() or 0,
        "tasks_completed_total": db.query(func.count(Task.id))
        .filter(Task.status == "completed")
        .scalar()
        or 0,
        "interactions_today": db.query(func.count(AgentInteraction.id))
        .filter(AgentInteraction.created_at >= day_ago)
        .scalar()
        or 0,
    }
    cache.set("platform_stats", data, ttl_seconds=300)  # 5 min global
    return envelope(data)
