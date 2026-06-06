import os
from dotenv import load_dotenv

load_dotenv()

# ── Gemini ─────────────────────────────────────────────────────────────────────
# Single source of truth — every agent imports GEMINI_MODEL from here.
# Zero hardcoded model strings anywhere else in the codebase.
GOOGLE_API_KEY: str = os.getenv("GOOGLE_API_KEY", "")
GEMINI_MODEL:   str = "gemini-2.5-flash"

# ── External services ──────────────────────────────────────────────────────────
TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")

SMTP_HOST:         str = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT:         int = int(os.getenv("SMTP_PORT", "587"))
EMAIL_ADDRESS:     str = os.getenv("EMAIL_ADDRESS", "")
EMAIL_APP_PASSWORD:str = os.getenv("EMAIL_APP_PASSWORD", "")

# ── Database ───────────────────────────────────────────────────────────────────
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./axolotl.db")

# ── Google OAuth ──────────────────────────────────────────────────────────────
GOOGLE_OAUTH_CLIENT_ID:     str  = os.getenv("GOOGLE_OAUTH_CLIENT_ID", "")
GOOGLE_OAUTH_CLIENT_SECRET: str  = os.getenv("GOOGLE_OAUTH_CLIENT_SECRET", "")
# Registered in Google Cloud Console → Credentials → Authorized redirect URIs
GOOGLE_OAUTH_REDIRECT_URI:  str  = os.getenv(
    "GOOGLE_OAUTH_REDIRECT_URI", "http://localhost:8000/auth/callback"
)
GOOGLE_OAUTH_SCOPES: list[str] = [
    "openid",
    "email",
    "profile",
    # Gmail and Calendar access — app stays in "testing" mode (≤100 test users)
    # until Google verification is obtained.  See README for setup.
    "https://www.googleapis.com/auth/gmail.modify",
    "https://www.googleapis.com/auth/calendar.events",
]

# ── Session / JWT ──────────────────────────────────────────────────────────────
JWT_SECRET:    str = os.getenv("JWT_SECRET", "change-me-in-production-please")
JWT_EXP_HOURS: int = int(os.getenv("JWT_EXP_HOURS", "24"))

# ── App ────────────────────────────────────────────────────────────────────────
FRONTEND_URL: str  = os.getenv("FRONTEND_URL", "http://localhost:5173")
# DEV_MODE=true allows the legacy X-User-Id header as auth fallback so seeded
# users can be tested without going through Google OAuth.
DEV_MODE:     bool = os.getenv("DEV_MODE", "false").lower() == "true"

# ── A2A Matchmaking ────────────────────────────────────────────────────────────
A2A_MATCH_THRESHOLD: float = float(os.getenv("A2A_MATCH_THRESHOLD", "0.55"))
A2A_MAX_TURNS:       int   = int(os.getenv("A2A_MAX_TURNS", "6"))
A2A_TURN_TOKENS:     int   = int(os.getenv("A2A_TURN_TOKENS", "512"))
A2A_COOLDOWN_DAYS:   int   = int(os.getenv("A2A_COOLDOWN_DAYS", "7"))
A2A_SCHEDULE_MINUTES:int   = int(os.getenv("A2A_SCHEDULE_MINUTES", "60"))
