"""Web Agent API — the canonical /web surface Jarvis delegates research to.

Thin HTTP adapters: /web/research drives the real local search->visit->synthesise
loop (services.web_research, free/no-key), and /web/findings reads the
opportunities the scout has already persisted (services.web_agent stores them).
No business logic lives here.
"""
import json
import time

from fastapi import APIRouter, Depends, Request
from fastapi.responses import JSONResponse, StreamingResponse
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.api.envelope import envelope
from app.core.db import get_db, SessionLocal
from app.core.logging import get_logger, log_event
from app.core.ratelimit import limiter
from app.core.security import get_current_user, decode_token
from app.models import User, WebScoutResult, WEB_CATEGORIES

logger = get_logger("axolot.web_api")
router = APIRouter(prefix="/web", tags=["web-agent"])


def _finding_payload(r: WebScoutResult) -> dict:
    return {
        "id": r.id,
        "title": r.title,
        "url": r.url,
        "summary": r.summary,
        "category": r.category,
        "relevance_score": r.relevance_score,
    }


@router.get("/stream")
def web_findings_stream(token: str = "", db: Session = Depends(get_db)):
    """Server-Sent Events stream of the user's web findings, one card at a time.

    EventSource can't send an Authorization header, so the JWT arrives as the
    `?token=` query param. If the scout hasn't run yet, it runs once (real
    Tavily/DDG search), then each finding is emitted as `data: {json}\\n\\n` so
    the UI can animate cards in as they arrive. A final `{"done": true}` closes."""
    try:
        user_id = decode_token(token).get("sub") if token else None
    except Exception:  # noqa: BLE001
        user_id = None
    if not user_id or not db.query(User).filter(User.id == user_id).first():
        return JSONResponse(status_code=401, content={"success": False, "error": "unauthorized"})

    def gen():
        s = SessionLocal()
        try:
            q = (
                s.query(WebScoutResult)
                .filter(WebScoutResult.user_id == user_id)
                .order_by(WebScoutResult.relevance_score.desc(), WebScoutResult.created_at.desc())
            )
            rows = q.limit(20).all()
            if not rows:
                # Nothing persisted yet — run the scout once, then re-read.
                try:
                    from app.services import web_agent

                    user = s.query(User).filter(User.id == user_id).first()
                    web_agent.run_report(s, user)
                    rows = q.limit(20).all()
                except Exception as exc:  # noqa: BLE001
                    log_event(logger, "web_stream_scout_failed", user_id=user_id, error=str(exc))
            for r in rows:
                yield f"data: {json.dumps(_finding_payload(r))}\n\n"
                time.sleep(0.12)  # paced so the client animates cards arriving
            yield f"data: {json.dumps({'done': True})}\n\n"
        finally:
            s.close()

    return StreamingResponse(
        gen(),
        media_type="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


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
