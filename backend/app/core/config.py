from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Optional

class Settings(BaseSettings):
    PROJECT_NAME: str = "Axolot"
    VERSION: str = "0.1.0"

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./axolot.db"
    SUPABASE_URL: str = "https://mock-supabase.co"
    SUPABASE_KEY: str = "mock-key"

    # Security
    SECRET_KEY: str = "default-secret-key-please-change-in-production"
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 11520  # 8 days

    # Google OAuth
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: Optional[str] = None

    # Gemini AI
    GEMINI_API_KEY: str = ""

    # Jarvis Configuration
    AGENT_NAME: str = "Jarvis"
    ORCHESTRATOR_MODEL: str = "gemini-2.5-flash"
    SUBAGENT_MODEL: str = "gemini-2.5-flash-lite"

    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True, extra="ignore")

settings = Settings()

