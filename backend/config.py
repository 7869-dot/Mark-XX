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
