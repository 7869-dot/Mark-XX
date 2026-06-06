import os
from dotenv import load_dotenv

load_dotenv()

ANTHROPIC_API_KEY: str = os.getenv("ANTHROPIC_API_KEY", "")
TAVILY_API_KEY: str = os.getenv("TAVILY_API_KEY", "")

SMTP_HOST: str = os.getenv("SMTP_HOST", "smtp.gmail.com")
SMTP_PORT: int = int(os.getenv("SMTP_PORT", "587"))
EMAIL_ADDRESS: str = os.getenv("EMAIL_ADDRESS", "")
EMAIL_APP_PASSWORD: str = os.getenv("EMAIL_APP_PASSWORD", "")

MODEL = "claude-sonnet-4-6"

# ── Database ───────────────────────────────────────────────────────────────────
DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./axolotl.db")

# ── A2A Matchmaking ────────────────────────────────────────────────────────────
# Minimum LLM-judge score (0-1) before a pair enters negotiation
A2A_MATCH_THRESHOLD: float = float(os.getenv("A2A_MATCH_THRESHOLD", "0.55"))
# Hard cap on total negotiation turns (split evenly between two agents)
A2A_MAX_TURNS: int = int(os.getenv("A2A_MAX_TURNS", "6"))
# Max tokens per negotiation turn (keeps costs bounded)
A2A_TURN_TOKENS: int = int(os.getenv("A2A_TURN_TOKENS", "512"))
# Days before the same pair can be re-evaluated
A2A_COOLDOWN_DAYS: int = int(os.getenv("A2A_COOLDOWN_DAYS", "7"))
# How often the background matchmaker runs (minutes)
A2A_SCHEDULE_MINUTES: int = int(os.getenv("A2A_SCHEDULE_MINUTES", "60"))
