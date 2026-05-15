from datetime import datetime
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from app.core.db import get_db
from app.core.security import create_access_token, create_refresh_token, rotate_refresh_token
from app.core.config import settings
from app.core.logging import get_logger, log_event
from app.core.ratelimit import limiter
from app.models import User
from app.schemas.auth import GoogleAuthRequest, RefreshRequest
from app.api.envelope import envelope
from app.services.agent_service import create_agent_for_user

logger = get_logger("axolot.auth")
router = APIRouter(prefix="/auth", tags=["auth"])


@router.post("/google")
@limiter.limit("20/minute")
def google_auth(request: Request, req: GoogleAuthRequest, db: Session = Depends(get_db)):
    """Stub mode accepts email+name directly. Live mode verifies a Google id_token."""
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
        # Live Google id_token verification.
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
        create_agent_for_user(db, user)  # agent creation atomically tied to registration
        log_event(logger, "user_registered", user_id=user.id)

    # Compensating safety: never let a user exist without an agent.
    if not user.agent:
        create_agent_for_user(db, user)
        log_event(logger, "agent_backfilled", user_id=user.id)

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
def refresh(req: RefreshRequest, db: Session = Depends(get_db)):
    access, new_refresh = rotate_refresh_token(req.refresh_token, db)
    from app.core.security import decode_token

    user_id = decode_token(access).get("sub")
    user = db.query(User).filter(User.id == user_id).first()
    if not user:
        raise HTTPException(status_code=401, detail="User not found")
    return envelope({
        "access_token": access,
        "refresh_token": new_refresh,
        "token_type": "bearer",
        "user_id": user.id,
        "onboarded": bool((user.onboarded or {}).get("completed")),
    }, agent_id=user.agent.id if user.agent else None)


@router.post("/logout")
def logout():
    return envelope({"ok": True})
