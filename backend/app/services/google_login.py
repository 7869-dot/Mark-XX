"""Google sign-in OAuth (openid email profile only).

Separate from google_auth.py, which handles the broader Gmail/Calendar offline
grant. This module owns just the authentication flow used by /auth/google/*.
Stub mode (USE_STUBS or missing client creds) fakes a deterministic identity so
local dev never needs real Google credentials.
"""
import hashlib

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger("axolot.google_login")

SCOPES = settings.LOGIN_OAUTH_SCOPES.split()


def is_stub() -> bool:
    return settings.USE_STUBS or not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET


def _flow():
    from google_auth_oauthlib.flow import Flow  # lazy

    flow = Flow.from_client_config(
        {
            "web": {
                "client_id": settings.GOOGLE_CLIENT_ID,
                "client_secret": settings.GOOGLE_CLIENT_SECRET,
                "auth_uri": "https://accounts.google.com/o/oauth2/auth",
                "token_uri": "https://oauth2.googleapis.com/token",
                "redirect_uris": [settings.GOOGLE_REDIRECT_URI],
            }
        },
        scopes=SCOPES,
    )
    flow.redirect_uri = settings.GOOGLE_REDIRECT_URI
    return flow


def build_login_url(state: str) -> str:
    """Consent URL for sign-in. In stub mode, points straight at the callback."""
    if is_stub():
        return f"{settings.GOOGLE_REDIRECT_URI}?state={state}&stub=1"

    url, _ = _flow().authorization_url(
        access_type="offline",
        include_granted_scopes="true",
        prompt="consent",
        state=state,
    )
    return url


def exchange_and_verify(code: str) -> dict:
    """Exchange the auth code, verify the id_token, return identity + refresh token.

    Keys: sub, email, name, picture, refresh_token.
    """
    if is_stub():
        fake = code or "stub"
        digest = hashlib.sha256(fake.encode()).hexdigest()[:12]
        return {
            "sub": f"stub-{digest}",
            "email": f"{digest}@stub.axolot.dev",
            "name": "Stub User",
            "picture": None,
            "refresh_token": f"stub-refresh-{digest}",
        }

    from google.oauth2 import id_token as google_id_token  # lazy
    from google.auth.transport import requests as google_requests

    flow = _flow()
    flow.fetch_token(code=code)
    creds = flow.credentials

    info = google_id_token.verify_oauth2_token(
        creds.id_token, google_requests.Request(), settings.GOOGLE_CLIENT_ID
    )
    return {
        "sub": info.get("sub"),
        "email": info["email"],
        "name": info.get("name") or info["email"].split("@")[0],
        "picture": info.get("picture"),
        "refresh_token": creds.refresh_token,
    }
