"""Web Agent API — the canonical /web surface Jarvis delegates research to.

Thin HTTP adapters: /web/research drives the real local search->visit->synthesise
loop (services.web_research, free/no-key), and /web/findings reads the
opportunities the scout has already persisted (services.web_agent stores them).
No business logic lives here.
"""
from fastapi import APIRouter, Depends, Request
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.envelope import envelope
from app.core.db import get_db
from app.core.ratelimit import limiter
from app.core.security import get_current_user
from app.models import User, WebScoutResult, WEB_CATEGORIES

router = APIRouter(prefix="/web", tags=["web-agent"])


class ResearchRequest(BaseModel):
    query: str = Field(..., min_length=1, max_length=1000)
    max_steps: int = 4


@router.post("/research")
@limiter.limit("10/minute")
def web_research(
    request: Request,
    body: ResearchRequest,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """Deep web research: search -> visit -> synthesise (local browser, no API
    key). Returns {answer, sources, steps, used_web}."""
    from app.services.web_research import deep_research

    result = deep_research(db, user, body.query.strip(), max_steps=max(1, min(6, body.max_steps)))
    return envelope(result)


@router.get("/findings")
@limiter.limit("60/minute")
def web_findings(
    request: Request,
    category: str | None = None,
    limit: int = 20,
    db: Session = Depends(get_db),
    user: User = Depends(get_current_user),
):
    """The opportunities the web scout has surfaced for this user, most relevant
    first. Optional ?category= filter. Returns {items[], categories}."""
    q = db.query(WebScoutResult).filter(WebScoutResult.user_id == user.id)
    if category and category in WEB_CATEGORIES:
        q = q.filter(WebScoutResult.category == category)
    rows = (
        q.order_by(WebScoutResult.relevance_score.desc(), WebScoutResult.created_at.desc())
        .limit(max(1, min(100, limit)))
        .all()
    )
    items = [
        {
            "id": r.id,
            "title": r.title,
            "url": r.url,
            "summary": r.summary,
            "category": r.category,
            "relevance_score": r.relevance_score,
            "feedback": r.feedback,
            "created_at": r.created_at.isoformat() if r.created_at else None,
        }
        for r in rows
    ]
    return envelope({"items": items, "categories": list(WEB_CATEGORIES)})
