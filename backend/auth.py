"""Authentication utilities — JWT creation/verification and OAuth token encryption.

Design
──────
• JWTs are short-lived (JWT_EXP_HOURS), HS256-signed with JWT_SECRET.
  They carry only the user's internal UUID as `sub`; no sensitive data.
• OAuth access/refresh tokens are encrypted at rest with Fernet (AES-128-CBC)
  using a key derived from JWT_SECRET via SHA-256.  Raw tokens are NEVER
  returned to the client or logged.
• get_valid_access_token() refreshes server-side and updates the DB row.

NEVER expose OAuthToken rows or their decrypted contents to API responses.
"""
from __future__ import annotations

import base64
import hashlib
import logging
from datetime import datetime, timedelta

import httpx
from cryptography.fernet import Fernet
from jose import JWTError, jwt
from sqlalchemy.orm import Session

from config import (
    GOOGLE_OAUTH_CLIENT_ID,
    GOOGLE_OAUTH_CLIENT_SECRET,
    JWT_EXP_HOURS,
    JWT_SECRET,
)

logger = logging.getLogger(__name__)

_JWT_ALGO = "HS256"


# ── Fernet key derived from JWT_SECRET ────────────────────────────────────────

def _fernet() -> Fernet:
    raw = hashlib.sha256(JWT_SECRET.encode()).digest()
    key = base64.urlsafe_b64encode(raw)
    return Fernet(key)


# ── Token encryption (at rest) ─────────────────────────────────────────────────

def encrypt_token(token: str) -> str:
    """Encrypt an OAuth token for DB storage."""
    return _fernet().encrypt(token.encode()).decode()


def decrypt_token(encrypted: str) -> str:
    """Decrypt an OAuth token retrieved from the DB."""
    return _fernet().decrypt(encrypted.encode()).decode()


# ── JWT ────────────────────────────────────────────────────────────────────────

def create_jwt(user_id: str) -> str:
    payload = {
        "sub": user_id,
        "iat": datetime.utcnow(),
        "exp": datetime.utcnow() + timedelta(hours=JWT_EXP_HOURS),
    }
    return jwt.encode(payload, JWT_SECRET, algorithm=_JWT_ALGO)


def verify_jwt(token: str) -> str:
    """Verify JWT and return the user_id (`sub` claim). Raises ValueError on failure."""
    try:
        payload = jwt.decode(token, JWT_SECRET, algorithms=[_JWT_ALGO])
        return payload["sub"]
    except JWTError as exc:
        raise ValueError(f"Invalid JWT: {exc}") from exc


# ── Access token refresh ───────────────────────────────────────────────────────

async def get_valid_access_token(user_id: str, db: Session) -> str:
    """
    Return a valid Google access token for user_id.
    Refreshes automatically if the stored token is within 5 minutes of expiry.
    Raises ValueError if no token row exists for this user.
    """
    from models import OAuthToken  # late import to avoid circular dependency

    row = db.query(OAuthToken).filter_by(user_id=user_id).first()
    if not row:
        raise ValueError(f"No OAuth token found for user {user_id}")

    # Still valid with headroom
    if datetime.utcnow() < row.expires_at - timedelta(minutes=5):
        return decrypt_token(row.access_token_enc)

    # Need to refresh
    if not row.refresh_token_enc:
        raise ValueError("No refresh token stored — user must re-authenticate")

    refresh_token = decrypt_token(row.refresh_token_enc)
    logger.info("Refreshing Google access token for user %s", user_id)

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            "https://oauth2.googleapis.com/token",
            data={
                "grant_type":    "refresh_token",
                "refresh_token": refresh_token,
                "client_id":     GOOGLE_OAUTH_CLIENT_ID,
                "client_secret": GOOGLE_OAUTH_CLIENT_SECRET,
            },
        )

    if not resp.is_success:
        raise ValueError(f"Token refresh failed: {resp.text}")

    new_tokens = resp.json()
    new_access  = new_tokens["access_token"]
    new_expires = datetime.utcnow() + timedelta(seconds=new_tokens.get("expires_in", 3600))

    row.access_token_enc = encrypt_token(new_access)
    row.expires_at       = new_expires
    row.updated_at       = datetime.utcnow()
    # Google may not return a new refresh token — keep the old one if absent
    if "refresh_token" in new_tokens:
        row.refresh_token_enc = encrypt_token(new_tokens["refresh_token"])
    db.commit()

    return new_access
