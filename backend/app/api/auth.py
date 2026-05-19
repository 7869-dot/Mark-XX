import secrets
from datetime import datetime

from fastapi import APIRouter, Depends, HTTPException, Request
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import (
    create_access_token,
    create_refresh_token,
    rotate_refresh_token,
    decode_token,
)
from app.core.config import settings
from app.core.logging import get_logger, log_event
from app.core.ratelimit import limiter
from app.models import User
from app.schemas.auth import GoogleAuthRequest
from app.api.envelope import envelope
from app.services.agent_service import create_agent_for_user
from app.services import google_login, google_auth

logger = get_logger("axolot.auth")
router = APIRouter(prefix="/auth", tags=["auth"])

REFRESH_COOKIE = "axolot_refresh"


def _set_refresh_cookie(response, token: str) -> None:
    response.set_cookie(
        key=REFRESH_COOKIE,
        value=token,
        httponly=True,
        secure=settings.COOKIE_SECURE,
        samesite=settings.COOKIE_SAMESITE,
        domain=settings.COOKIE_DOMAIN or None,
        max_age=settings.REFRESH_TOKEN_EXPIRE_DAYS * 86400,
        path="/",
    )


def _ensure_agent(db: Session, user: User) -> None:
    if not user.agent:
        create_agent_for_user(db, user)
        log_event(logger, "agent_backfilled", user_id=user.id)


# ── Google sign-in (authorization-code flow) ───────────────────────────────
@router.get("/google/redirect")
def google_redirect():
    """Kick off Google sign-in: redirect the browser to Google's consent screen."""
    state = secrets.token_urlsafe(24)
    return RedirectResponse(url=google_login.build_login_url(state))


@router.get("/google/callback")
def google_callback(
    request: Request,
    code: str = "",
    state: str = "",
    stub: int = 0,
    db: Session = Depends(get_db),
):
    """Google redirects here after consent. Exchange code → JWT, set cookie,
    bounce to the frontend dashboard with the access token in the URL."""
    fail_url = f"{settings.FRONTEND_URL}/?error=oauth_failed"
    try:
        identity = google_login.exchange_and_verify(code or f"stub-{state}")
    except Exception as exc:  # noqa: BLE001
        log_event(logger, "google_login_failed", error=str(exc))
        return RedirectResponse(url=fail_url)

    email = identity.get("email")
    if not email:
        return RedirectResponse(url=fail_url)

    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(
            email=email,
            name=identity.get("name") or email.split("@")[0],
            avatar_url=identity.get("picture"),
            google_id=identity.get("sub"),
        )
        db.add(user)
        db.commit()
        db.refresh(user)
        create_agent_for_user(db, user)
        log_event(logger, "user_registered", user_id=user.id)
    else:
        if identity.get("picture"):
            user.avatar_url = identity["picture"]
        if identity.get("sub") and not user.google_id:
            user.google_id = identity["sub"]

    _ensure_agent(db, user)

    # Persist the sign-in refresh token (openid scope only). Never clobber a
    # richer Gmail/Calendar grant — that flow owns google_refresh_token when a
    # broader scope has been authorized.
    rt = identity.get("refresh_token")
    if rt and not (user.gmail_connected or user.calendar_connected):
        user.google_refresh_token = google_auth.encrypt(rt)

    user.last_login_at = datetime.utcnow()
    db.commit()

    access = create_access_token(user.id)
    refresh = create_refresh_token(user.id, db)

    resp = RedirectResponse(url=f"{settings.FRONTEND_URL}/dashboard?token={access}")
    _set_refresh_cookie(resp, refresh)
    return resp


# ── Legacy / programmatic token grant (kept for stub + tests) ──────────────
@router.post("/google")
@limiter.limit("20/minute")
def google_auth_post(request: Request, req: GoogleAuthRequest, db: Session = Depends(get_db)):
    """Direct token grant. Stub mode accepts email+name; live mode verifies an id_token."""
    email = req.email
    name = req.name or "Guest"
    avatar_url = req.avatar_url
    google_id = None

    if settings.USE_STUBS or not settings.GOOGLE_CLIENT_ID:
        if not email:
            raise HTTPException(status_code=400, detail="Email required in stub mode")
    else:
        if not req.id_token:
            raise HTTPException(status_code=400, detail="id_token required")
        try:
            from google.oauth2 import id_token as google_id_token  # type: ignore
            from google.auth.transport import requests as google_requests  # type: ignore

            info = google_id_token.verify_oauth2_token(
                req.id_token, google_requests.Request(), settings.GOOGLE_CLIENT_ID
            )
            email = info["email"]
            name = info.get("name", email.split("@")[0])
            avatar_url = info.get("picture")
            google_id = info.get("sub")
        except Exception as exc:  # noqa: BLE001
            raise HTTPException(status_code=401, detail=f"Google verification failed: {exc}")

    user = db.query(User).filter(User.email == email).first()
    if not user:
        user = User(email=email, name=name, avatar_url=avatar_url, google_id=google_id)
        db.add(user)
        db.commit()
        db.refresh(user)
        create_agent_for_user(db, user)
        log_event(logger, "user_registered", user_id=user.id)

    _ensure_agent(db, user)

    user.last_login_at = datetime.utcnow()
    db.commit()

    onboarded = bool((user.onboarded or {}).get("completed"))
    return envelope(
        {
            "access_token": create_access_token(user.id),
            "refresh_token": create_refresh_token(user.id, db),
            "token_type": "bearer",
            "user_id": user.id,
            "onboarded": onboarded,
        },
        agent_id=user.agent.id if user.agent else None,
    )


@router.post("/refresh")
async def refresh(request: Request, db: Session = Depends(get_db)):
    """Rotate the refresh token. Reads it from the httpOnly cookie (preferred)
    or a JSON body (legacy clients). Returns a fresh access token + sets the
    rotated refresh cookie."""
    token = request.cookies.get(REFRESH_COOKIE)
    if not token:
        try:
            body = await request.json()
            token = (body or {}).get("refresh_token")
        except Exception:  # noqa: BLE001
            token = None
    if not token:
        raise HTTPException(status_code=401, detail="No refresh token")

    access, new_refresh = rotate_refresh_token(token, db)
    user_id = decode_token(access).get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")

    from fastapi.responses import JSONResponse

    payload = envelope(
        {
            "access_token": access,
            "refresh_token": new_refresh,
            "token_type": "bearer",
            "user_id": user.id,
            "onboarded": bool((user.onboarded or {}).get("completed")),
        },
        agent_id=user.agent.id if user.agent else None,
    )
    resp = JSONResponse(content=payload)
    _set_refresh_cookie(resp, new_refresh)
    return resp


@router.post("/logout")
def logout():
    from fastapi.responses import JSONResponse

    resp = JSONResponse(content=envelope({"ok": True}))
    resp.delete_cookie(REFRESH_COOKIE, domain=settings.COOKIE_DOMAIN or None, path="/")
    return resp
