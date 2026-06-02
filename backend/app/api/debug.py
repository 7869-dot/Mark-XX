"""Admin debug endpoints — gated by X-Debug-Secret header.

These are intentionally separate from the user-facing router so a misconfigured
deploy can't accidentally expose them via the regular auth scheme. The secret
falls back to the JWT_SECRET so it's never blank in dev, but in production we
expect operators to set DEBUG_SECRET explicitly.
"""
from fastapi import APIRouter, Depends, Header, HTTPException
from sqlalchemy.orm import Session

from app.api.envelope import envelope
from app.core.config import settings
from app.core.db import get_db
from app.core.logging import get_logger

router = APIRouter(prefix="/debug", tags=["debug"])
logger = get_logger("axolot.debug")


def _check_secret(x_debug_secret: str | None) -> None:
    expected = (
        getattr(settings, "DEBUG_SECRET", None)
        or settings.JWT_SECRET
    )
    if not expected or x_debug_secret != expected:
        raise HTTPException(status_code=403, detail="forbidden")


@router.post("/classify-now")
def classify_now(
    x_debug_secret: str | None = Header(default=None, alias="X-Debug-Secret"),
    db: Session = Depends(get_db),
):
    """Run the email classifier across every connected user, synchronously."""
    _check_secret(x_debug_secret)
    from app.models import User
    from app.services.email_classifier import classify_recent_for_user

    out: dict[str, int] = {}
    for u in db.query(User).all():
        if not getattr(u, "gmail_connected", False):
            continue
        try:
            out[u.id] = classify_recent_for_user(db, u)
        except Exception as exc:  # noqa: BLE001
            out[u.id] = -1
            logger.error("classify_now failed user=%s err=%s", u.id, exc)
    return envelope({"per_user": out, "total_users": len(out)})


@router.post("/process-a2a-now")
def process_a2a_now(
    x_debug_secret: str | None = Header(default=None, alias="X-Debug-Secret"),
    db: Session = Depends(get_db),
):
    """Process every unread A2A message right now."""
    _check_secret(x_debug_secret)
    from app.services.a2a_async import process_all_unread

    return envelope({"replied": process_all_unread(db)})


@router.get("/gmail-raw")
def gmail_raw(
    user_id: str,
    x_debug_secret: str | None = Header(default=None, alias="X-Debug-Secret"),
    db: Session = Depends(get_db),
):
    """Dump the raw list_emails output for a user — diagnoses MCP/Gmail issues."""
    _check_secret(x_debug_secret)
    from app.services import gmail_service

    try:
        emails = gmail_service.list_emails(db, user_id, max_results=15)
    except Exception as exc:  # noqa: BLE001
        raise HTTPException(status_code=502, detail=f"gmail_call_failed: {exc}")
    return envelope({"count": len(emails), "emails": emails})


@router.get("/gemini-ping")
def gemini_ping(
    x_debug_secret: str | None = Header(default=None, alias="X-Debug-Secret"),
):
    """End-to-end Gemini probe. Returns the live model output, the key status,
    and the resolved stub flag — diagnoses "why is chat returning the stub
    fallback?" in one call."""
    _check_secret(x_debug_secret)
    key_present = bool(settings.GEMINI_API_KEY)
    out: dict = {
        "use_stubs": bool(settings.USE_STUBS),
        "gemini_key_present": key_present,
        "gemini_key_tail": (settings.GEMINI_API_KEY or "")[-4:] if key_present else None,
        "model": "gemini-2.0-flash",
        "ok": False,
        "response": None,
        "error": None,
    }
    if not key_present:
        out["error"] = "GEMINI_API_KEY not set"
        return envelope(out)
    try:
        from google import genai  # google-genai SDK

        client = genai.Client(api_key=settings.GEMINI_API_KEY)
        resp = client.models.generate_content(
            model="gemini-2.0-flash", contents="Say hello in one word."
        )
        out["ok"] = True
        out["response"] = getattr(resp, "text", "") or ""
    except Exception as exc:  # noqa: BLE001
        out["error"] = f"{type(exc).__name__}: {exc}"
    return envelope(out)


@router.get("/schema")
def schema_dump(
    x_debug_secret: str | None = Header(default=None, alias="X-Debug-Secret"),
    db: Session = Depends(get_db),
):
    """Confirm new tables/columns exist in the live DB."""
    _check_secret(x_debug_secret)
    from sqlalchemy import inspect
    from app.core.db import engine

    insp = inspect(engine)
    tables = sorted(insp.get_table_names())
    cols = {
        t: [c["name"] for c in insp.get_columns(t)]
        for t in (
            "agents",
            "user_personalities",
            "classified_emails",
            "agent_messages",
            "agent_activity_log",
        )
        if t in tables
    }
    return envelope({"tables": tables, "columns": cols})
