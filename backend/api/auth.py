"""Google OAuth 2.0 login flow and session endpoints.

Flow
────
1. GET /auth/login  → redirect browser to Google consent screen
2. Google redirects to GET /auth/callback?code=...&state=...
3. Backend exchanges code, fetches userinfo, creates/updates User + OAuthToken
4. Backend issues JWT, redirects browser to FRONTEND_URL/?token=<jwt>
5. Frontend stores JWT in localStorage, sends as `Authorization: Bearer <jwt>`

Security notes
──────────────
• state nonce validated at callback to prevent CSRF.
• access_type=offline + prompt=consent ensures a refresh_token is returned.
• Raw tokens encrypted at rest; NEVER returned in any API response.
• The JWT carries only user_id (sub) — no email, no token.
"""
from __future__ import annotations

import logging
import secrets
import time
from datetime import datetime, timedelta
from urllib.parse import urlencode

import httpx
from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import RedirectResponse
from sqlalchemy.orm import Session

from auth import create_jwt, encrypt_token, verify_jwt
from config import (
    FRONTEND_URL,
    GOOGLE_OAUTH_CLIENT_ID,
    GOOGLE_OAUTH_CLIENT_SECRET,
    GOOGLE_OAUTH_REDIRECT_URI,
    GOOGLE_OAUTH_SCOPES,
    DEV_MODE,
)
from db import get_db
from models import OAuthToken, User

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/auth", tags=["auth"])

# In-memory state store (CSRF protection).
# TTL: 5 minutes. Replace with Redis for multi-process production.
_pending_states: dict[str, float] = {}


# ── Login ──────────────────────────────────────────────────────────────────────

@router.get("/login")
async def login():
    """Redirect the browser to Google's OAuth consent page."""
    state = secrets.token_urlsafe(20)
    _pending_states[state] = time.time()

    # Prune stale states (simple housekeeping)
    cutoff = time.time() - 600
    for k in list(_pending_states):
        if _pending_states[k] < cutoff:
            del _pending_states[k]

    params = {
        "client_id":     GOOGLE_OAUTH_CLIENT_ID,
        "redirect_uri":  GOOGLE_OAUTH_REDIRECT_URI,
        "response_type": "code",
        "scope":         " ".join(GOOGLE_OAUTH_SCOPES),
        "access_type":   "offline",   # get refresh_token
        "prompt":        "consent",   # always re-consent so refresh_token is issued
        "state":         state,
    }
    return RedirectResponse(
        f"https://accounts.google.com/o/oauth2/v2/auth?{urlencode(params)}"
    )


# ── OAuth Callback ─────────────────────────────────────────────────────────────

@router.get("/callback")
async def callback(
    code:  str = Query(...),
    state: str = Query(...),
    db:    Session = Depends(get_db),
):
    """
    Google redirects here after the user authorizes.
    Exchanges code for tokens, creates/updates the user, issues a JWT,
    then redirects back to the frontend.
    """
    # ── CSRF / state check ─────────────────────────────────────────────────
    ts = _pending_states.pop(state, None)
    if ts is None or time.time() - ts > 300:
        raise HTTPException(status_code=400, detail="Invalid or expired OAuth state")

    # ── Token exchange ─────────────────────────────────────────────────────
    async with httpx.AsyncClient() as client:
        token_resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "grant_type":    "authorization_code",
                "code":          code,
                "redirect_uri":  GOOGLE_OAUTH_REDIRECT_URI,
                "client_id":     GOOGLE_OAUTH_CLIENT_ID,
                "client_secret": GOOGLE_OAUTH_CLIENT_SECRET,
            },
        )
        if not token_resp.is_success:
            logger.error("Token exchange failed: %s", token_resp.text)
            raise HTTPException(status_code=400, detail="Google token exchange failed")
        tokens = token_resp.json()

        # ── Fetch userinfo ─────────────────────────────────────────────────
        ui_resp = await client.get(
            "https://www.googleapis.com/oauth2/v3/userinfo",
            headers={"Authorization": f"Bearer {tokens['access_token']}"},
        )
        if not ui_resp.is_success:
            raise HTTPException(status_code=400, detail="Failed to fetch Google user info")
        info = ui_resp.json()

    google_sub   = info["sub"]
    email        = info.get("email", "")
    display_name = info.get("name", "") or info.get("given_name", "") or email.split("@")[0]

    # ── Find or create user ────────────────────────────────────────────────
    user = db.query(User).filter(User.google_sub == google_sub).first()
    if not user:
        user = User(
            display_name = display_name,
            google_sub   = google_sub,
            email        = email,
        )
        db.add(user)
        db.flush()
        logger.info("New user created via OAuth: %s (%s)", user.id, email)
    else:
        # Refresh display name in case it changed
        user.display_name = display_name

    # ── Upsert OAuth tokens (encrypted) ───────────────────────────────────
    access_token  = tokens["access_token"]
    refresh_token = tokens.get("refresh_token", "")
    expires_at    = datetime.utcnow() + timedelta(
        seconds=tokens.get("expires_in", 3600)
    )

    token_row = db.query(OAuthToken).filter_by(user_id=user.id).first()
    if token_row:
        token_row.access_token_enc = encrypt_token(access_token)
        token_row.expires_at       = expires_at
        token_row.updated_at       = datetime.utcnow()
        if refresh_token:
            token_row.refresh_token_enc = encrypt_token(refresh_token)
    else:
        db.add(OAuthToken(
            user_id           = user.id,
            access_token_enc  = encrypt_token(access_token),
            refresh_token_enc = encrypt_token(refresh_token) if refresh_token else "",
            scopes            = " ".join(GOOGLE_OAUTH_SCOPES),
            expires_at        = expires_at,
        ))

    db.commit()

    # ── Issue JWT and redirect ─────────────────────────────────────────────
    jwt_token = create_jwt(user.id)
    # Token is passed in URL query param; frontend reads + removes it immediately.
    # Using a fragment (#token=...) would be more secure but requires extra
    # frontend handling; query param is fine for localhost dev.
    return RedirectResponse(f"{FRONTEND_URL}/?token={jwt_token}")


# ── Me / Logout ────────────────────────────────────────────────────────────────

@router.get("/me")
async def me(
    authorization: str | None = None,
    db: Session = Depends(get_db),
):
    """Return basic info about the currently authenticated user."""
    from fastapi import Header as _Header
    # Can't use Depends(get_current_user_id) here to avoid circular import;
    # parse the Authorization header directly.
    from auth import verify_jwt as _verify

    if not authorization:
        raise HTTPException(status_code=401, detail="Not authenticated")

    token = authorization.removeprefix("Bearer ").strip()
    try:
        user_id = _verify(token)
    except ValueError:
        raise HTTPException(status_code=401, detail="Invalid token")

    user = db.get(User, user_id)
    if not user:
        raise HTTPException(status_code=404, detail="User not found")

    return {
        "id":           user.id,
        "display_name": user.display_name,
        "email":        user.email,
    }


@router.post("/logout")
async def logout():
    """JWT is stateless — client deletes it; we just confirm."""
    return {"ok": True, "message": "Delete your JWT to complete logout."}
