from functools import lru_cache
from pydantic import field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

import os

class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    DATABASE_URL: str = os.environ.get("DATABASE_URL", "sqlite:///./axolot.db")

    @field_validator("DATABASE_URL")
    @classmethod
    def _normalize_db_url(cls, v: str) -> str:
        if v.startswith("postgres://"):
            return v.replace("postgres://", "postgresql+psycopg2://", 1)
        if v.startswith("postgresql://"):
            return v.replace("postgresql://", "postgresql+psycopg2://", 1)
        return v
    GEMINI_API_KEY: str = ""
    GOOGLE_CLIENT_ID: str = ""
    GOOGLE_CLIENT_SECRET: str = ""

    # Canonical secret. Render sets SECRET_KEY; legacy code reads JWT_SECRET.
    SECRET_KEY: str = ""
    JWT_SECRET: str = "dev-jwt-secret-change-me"
    JWT_REFRESH_SECRET: str = "dev-refresh-secret-change-me"
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 15
    REFRESH_TOKEN_EXPIRE_DAYS: int = 30
    FRONTEND_URL: str = "https://axolot.vercel.app"
    AXOLOT_BACKEND_URL: str = "http://localhost:8000"
    SCHEDULER_TIMEZONE: str = "UTC"
    USE_STUBS: bool = True

    # Login OAuth (Google sign-in) — distinct from the Gmail/Calendar grant.
    GOOGLE_REDIRECT_URI: str = "http://localhost:8000/auth/google/callback"
    LOGIN_OAUTH_SCOPES: str = "openid email profile"

    # Gmail + Calendar offline grant (broader, restricted scopes). Both point at
    # the single /integrations/google/callback handler.
    GMAIL_REDIRECT_URI: str = ""
    CALENDAR_REDIRECT_URI: str = ""
    GOOGLE_OAUTH_SCOPES: str = (
        "openid email profile "
        "https://www.googleapis.com/auth/gmail.modify "
        "https://www.googleapis.com/auth/calendar"
    )

    # Fernet key for encrypting Google tokens at rest. Render sets ENCRYPTION_KEY;
    # legacy code reads TOKEN_ENC_KEY. Empty -> derived dev key.
    ENCRYPTION_KEY: str = ""
    TOKEN_ENC_KEY: str = ""

    # Refresh-token cookie.
    COOKIE_DOMAIN: str = ""
    COOKIE_SECURE: bool = True
    COOKIE_SAMESITE: str = "lax"

    @model_validator(mode="after")
    def _reconcile_aliases(self):
        # Render provisions SECRET_KEY / ENCRYPTION_KEY; the rest of the codebase
        # was written against JWT_SECRET / TOKEN_ENC_KEY. Bridge them here so
        # neither side needs to change.
        if self.SECRET_KEY:
            self.JWT_SECRET = self.SECRET_KEY
            if self.JWT_REFRESH_SECRET == "dev-refresh-secret-change-me":
                self.JWT_REFRESH_SECRET = f"{self.SECRET_KEY}-refresh"
        if self.ENCRYPTION_KEY and not self.TOKEN_ENC_KEY:
            self.TOKEN_ENC_KEY = self.ENCRYPTION_KEY
        if not self.GMAIL_REDIRECT_URI:
            self.GMAIL_REDIRECT_URI = f"{self.AXOLOT_BACKEND_URL}/integrations/google/callback"
        if not self.CALENDAR_REDIRECT_URI:
            self.CALENDAR_REDIRECT_URI = self.GMAIL_REDIRECT_URI
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
