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

# ── A2A Matchmaking ────────────────────────────────────────────────────────────
A2A_MATCH_THRESHOLD: float = float(os.getenv("A2A_MATCH_THRESHOLD", "0.55"))
A2A_MAX_TURNS:       int   = int(os.getenv("A2A_MAX_TURNS", "6"))
A2A_TURN_TOKENS:     int   = int(os.getenv("A2A_TURN_TOKENS", "512"))
A2A_COOLDOWN_DAYS:   int   = int(os.getenv("A2A_COOLDOWN_DAYS", "7"))
A2A_SCHEDULE_MINUTES:int   = int(os.getenv("A2A_SCHEDULE_MINUTES", "60"))
