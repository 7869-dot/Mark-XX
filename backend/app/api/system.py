from datetime import datetime, timedelta
from fastapi import APIRouter, Depends, Response
from sqlalchemy.orm import Session
from sqlalchemy import func, text

from app.core.db import get_db
from app.core.cache import cache
from app.models import Agent, Task
from app.api.envelope import envelope
from app.services.gemini import ping as gemini_ping


router = APIRouter(tags=["system"])


def _check_database(db: Session) -> bool:
    try:
        db.execute(text("SELECT 1"))
        return True
    except Exception:  # noqa: BLE001
        return False


def _check_scheduler() -> bool:
    try:
        from app.main import scheduler  # late import to avoid cycle

        return bool(scheduler.running)
    except Exception:  # noqa: BLE001
        return False


def _check_gemini() -> bool:
    try:
        return gemini_ping()
    except Exception:  # noqa: BLE001
        return False


# Render's uptime monitor hits /health. Keep it cheap and dependency-light —
# only the DB and scheduler need to be up for the app to serve traffic. A
# transient Gemini outage shouldn't bounce the service.
@router.get("/health")
def health(response: Response, db: Session = Depends(get_db)):
    """Lightweight liveness probe — DB + scheduler only (used by Render)."""
    checks = {"database": _check_database(db), "scheduler": _check_scheduler()}
    ok = all(checks.values())
    if not ok:
        response.status_code = 503
    return envelope({
        "status": "ok" if ok else "degraded",
        "checks": checks,
        "timestamp": datetime.utcnow().isoformat(),
    })


# Deeper check for human operators and dashboards — includes Gemini, which can
# blip independently of the app being able to serve cached/stub responses.
@router.get("/health/full")
def health_full(response: Response, db: Session = Depends(get_db)):
    """Full health check — DB + scheduler + Gemini. Not for uptime monitoring."""
    checks = {
        "database": _check_database(db),
        "scheduler": _check_scheduler(),
        "gemini": _check_gemini(),
    }
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
    data = {
        "total_agents": db.query(func.count(Agent.id)).scalar() or 0,
        "tasks_completed_total": db.query(func.count(Task.id))
        .filter(Task.status == "completed")
        .scalar()
        or 0,
    }
    cache.set("platform_stats", data, ttl_seconds=300)  # 5 min global
    return envelope(data)
