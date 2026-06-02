"""Google credential management: encrypted token storage, auto-refresh, OAuth flow.

Stub-fallback: when USE_STUBS or no GOOGLE_CLIENT_ID, the OAuth flow is faked
and get_google_credentials() returns None (gmail/calendar services then serve
stub data). Tokens are always stored Fernet-encrypted at rest.
"""
import base64
import hashlib
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger, log_event
from app.models import User

logger = get_logger("axolot.google_auth")

SCOPES = settings.GOOGLE_OAUTH_SCOPES.split()


def is_stub() -> bool:
    return settings.USE_STUBS or not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET


def _reauth_reason(exc: Exception) -> str | None:
    """Map a refresh failure to a disconnect reason that requires the user to
    re-consent, or None for transient errors worth retrying. Covers both an
    expired/revoked refresh token (invalid_grant) and a bad/again-required scope
    grant (invalid_scope) — both mean the stored grant is unusable."""
    s = str(exc).lower()
    if "invalid_scope" in s:
        return "invalid_scope"
    if "invalid_grant" in s or "expired or revoked" in s:
        return "token_expired"
    return None


def mark_disconnected(db: Session, user: User, reason: str = "token_expired") -> None:
    """Flag Google as disconnected so the agent stops trying and the UI can
    prompt a reconnect. Keeps the (now-useless) tokens; a re-consent overwrites
    them via store_tokens, which clears the reason."""
    user.gmail_connected = False
    user.calendar_connected = False
    user.google_disconnect_reason = reason
    db.commit()
    log_event(logger, "google_disconnected", user_id=user.id, reason=reason)


def is_connected(user: User) -> bool:
    """Whether Google is usable for this user right now."""
    if is_stub():
        return bool(user.gmail_connected or user.calendar_connected)
    return bool((user.gmail_connected or user.calendar_connected) and not user.google_disconnect_reason)


# ── Encryption at rest ─────────────────────────────────────────────────────
def _fernet():
    from cryptography.fernet import Fernet

    key = settings.TOKEN_ENC_KEY
    if not key:
        # Deterministic dev key derived from JWT_SECRET. Set TOKEN_ENC_KEY in prod.
        digest = hashlib.sha256(settings.JWT_SECRET.encode()).digest()
        key = base64.urlsafe_b64encode(digest).decode()
    return Fernet(key.encode() if isinstance(key, str) else key)


def encrypt(plain: str | None) -> str | None:
    if plain is None:
        return None
    return _fernet().encrypt(plain.encode()).decode()


def decrypt(token: str | None) -> str | None:
    if not token:
        return None
    try:
        return _fernet().decrypt(token.encode()).decode()
    except Exception:  # noqa: BLE001
        return None


# ── Token persistence ──────────────────────────────────────────────────────
def store_tokens(
    db: Session,
    user: User,
    access_token: str | None,
    refresh_token: str | None,
    expiry: datetime | None,
    scopes: str | None,
) -> None:
    user.google_access_token = encrypt(access_token)
    # Google only returns a refresh_token on first consent — keep the old one
    # if a re-auth didn't include one.
    if refresh_token:
        user.google_refresh_token = encrypt(refresh_token)
    user.google_token_expiry = expiry
    if scopes:
        user.google_scopes = scopes
    granted = scopes or ""
    user.gmail_connected = "gmail" in granted
    user.calendar_connected = "calendar" in granted
    # A fresh (re)connect clears any prior disconnect reason.
    user.google_disconnect_reason = None
    db.commit()
    log_event(
        logger, "google_tokens_stored",
        user_id=user.id, gmail=user.gmail_connected, calendar=user.calendar_connected,
    )


def revoke_google_access(db: Session, user: User) -> None:
    user.google_access_token = None
    user.google_refresh_token = None
    user.google_token_expiry = None
    user.google_scopes = None
    user.gmail_connected = False
    user.calendar_connected = False
    user.google_disconnect_reason = None  # explicit user disconnect, not an error
    db.commit()
    log_event(logger, "google_access_revoked", user_id=user.id)


def check_token_health(db: Session, user: User) -> dict:
    if is_stub():
        return {"valid": bool(user.gmail_connected or user.calendar_connected),
                "expires_in_minutes": 999999, "stub": True}
    if not user.google_refresh_token:
        return {"valid": False, "expires_in_minutes": 0}
    expiry = user.google_token_expiry
    if not expiry:
        return {"valid": True, "expires_in_minutes": 0}
    delta = (expiry - datetime.utcnow()).total_seconds() / 60
    return {"valid": delta > 0, "expires_in_minutes": int(delta)}


# ── Credentials ────────────────────────────────────────────────────────────
def get_google_credentials(db: Session, user: User):
    """Build google Credentials from stored tokens; auto-refresh + persist.

    Returns None in stub mode (callers fall back to stub data).
    """
    if is_stub():
        return None
    refresh = decrypt(user.google_refresh_token)
    if not refresh:
        return None

    from google.oauth2.credentials import Credentials  # lazy
    from google.auth.transport.requests import Request

    creds = Credentials(
        token=decrypt(user.google_access_token),
        refresh_token=refresh,
        token_uri="https://oauth2.googleapis.com/token",
        client_id=settings.GOOGLE_CLIENT_ID,
        client_secret=settings.GOOGLE_CLIENT_SECRET,
        scopes=(user.google_scopes or settings.GOOGLE_OAUTH_SCOPES).split(),
    )
    if user.google_token_expiry:
        creds.expiry = user.google_token_expiry

    if not creds.valid:
        try:
            creds.refresh(Request())
            user.google_access_token = encrypt(creds.token)
            user.google_token_expiry = creds.expiry
            db.commit()
            log_event(logger, "google_token_refreshed", user_id=user.id)
        except Exception as exc:  # noqa: BLE001
            log_event(logger, "google_token_refresh_failed", user_id=user.id, error=str(exc))
            # invalid_grant (expired/revoked) OR invalid_scope (bad grant) — mark
            # disconnected so the agent stops retrying and the UI prompts reconnect.
            reason = _reauth_reason(exc)
            if reason:
                mark_disconnected(db, user, reason)
            return None
    return creds


# ── OAuth authorization-code flow ──────────────────────────────────────────
def build_authorization_url(state: str) -> str:
    """Consent URL for the offline Gmail+Calendar grant."""
    if is_stub():
        # Frontend can just hit the callback directly with ?stub=1 in dev.
        return f"{settings.GMAIL_REDIRECT_URI}?state={state}&stub=1"

    from google_auth_oauthlib.flow import Flow  # lazy

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.GMAIL_REDIRECT_URI],
            }
        },
        scopes=SCOPES,
    )
    flow.redirect_uri = settings.GMAIL_REDIRECT_URI
    url, _ = flow.authorization_url(
        access_type="offline", include_granted_scopes="true",
        prompt="consent", state=state,
    )
    return url


def exchange_code(code: str) -> dict:
    """Exchange an auth code for tokens. Returns dict for store_tokens()."""
    if is_stub():
        return {
            "access_token": f"stub-access-{code}",
            "refresh_token": f"stub-refresh-{code}",
            "expiry": datetime.utcnow() + timedelta(hours=1),
            "scopes": settings.GOOGLE_OAUTH_SCOPES,
        }

    from google_auth_oauthlib.flow import Flow  # lazy

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.GMAIL_REDIRECT_URI],
            }
        },
        scopes=SCOPES,
    )
    flow.redirect_uri = settings.GMAIL_REDIRECT_URI
    flow.fetch_token(code=code)
    creds = flow.credentials
    return {
        "access_token": creds.token,
        "refresh_token": creds.refresh_token,
        "expiry": creds.expiry,
        "scopes": " ".join(creds.scopes or SCOPES),
    }
