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

    # ── LLM gateway ──────────────────────────────────────────────────────────
    # The provider/model are config, never hardcoded in business logic, so the
    # Phase-3 move to self-hosted GPUs (RunPod/vLLM) or the proprietary Axolot
    # model is a deploy-var change, not a code rewrite. See services/llm_gateway.
    #   LLM_PROVIDER: "gemini" (default) | "local" (any OpenAI-compatible server)
    #   LLM_MODEL:    model id passed to whichever provider is active
    LLM_PROVIDER: str = "gemini"
    # Lite tier — the cheap default for email parsing, post generation, chat.
    LLM_MODEL: str = "gemini-2.0-flash-lite"

    # ── Tiered models (Jarvis overhaul) ──────────────────────────────────────
    # Routed per task by llm_gateway._model_for(): light tasks (email parsing,
    # post generation, plain chat) -> LIGHT; relevance ranking / research /
    # grounded synthesis -> HEAVY; Jarvis's multi-step orchestration briefing ->
    # ULTRA. Real, current Gemini model IDs (verified names):
    #   lite  = gemini-2.0-flash-lite   (LIGHT default)
    #   flash = gemini-2.5-flash        (a mid option; set via LLM_MODEL_* if wanted)
    #   pro   = gemini-2.5-pro          (HEAVY/ULTRA default)
    # All env-overridable. A bad/unknown id is caught by validate_models() at
    # boot (logged loudly) and degrades gracefully to the stub at runtime.
    LLM_MODEL_LIGHT: str = ""               # empty -> falls back to LLM_MODEL
    LLM_MODEL_HEAVY: str = "gemini-2.5-pro"
    LLM_MODEL_ULTRA: str = "gemini-2.5-pro"

    def model_light(self) -> str:
        return self.LLM_MODEL_LIGHT or self.LLM_MODEL

    def model_heavy(self) -> str:
        return self.LLM_MODEL_HEAVY or self.model_light()

    def model_ultra(self) -> str:
        return self.LLM_MODEL_ULTRA or self.model_heavy()
    # OpenAI-compatible endpoint for the "local" provider (vLLM/TGI on RunPod,
    # or the eventual fine-tuned Axolot model behind the same wire format).
    LLM_BASE_URL: str = ""          # e.g. https://<pod>.runpod.net/v1
    LLM_API_KEY: str = ""           # bearer for the local/self-hosted endpoint
    LLM_TIMEOUT_SECONDS: float = 30.0

    # ── Agent web access (Sprint 6) ──────────────────────────────────────────
    # Live web search for grounded posts + the web scout. Default provider is
    # "duckduckgo" — a FREE, no-API-key path that drives a local headless browser
    # (Playwright) with an httpx+BeautifulSoup fallback (see services.local_browser).
    # "tavily"/"serpapi" remain available for those who set a key. With USE_STUBS
    # (dev/tests) every provider short-circuits to deterministic stubs, so the
    # feature works end-to-end with no external dep and no browser install.
    WEB_SEARCH_PROVIDER: str = "duckduckgo"   # duckduckgo (local, free) | tavily | serpapi
    TAVILY_API_KEY: str = ""
    SERPAPI_API_KEY: str = ""
    WEB_FETCH_TIMEOUT_SECONDS: float = 8.0

    # ── Local headless browser (free search + scraping) ──────────────────────
    # Run Chromium headless on this machine — no paid API. Falls back to a plain
    # httpx+BS4 fetch when Playwright/Chromium isn't installed, then to stubs.
    BROWSER_HEADLESS: bool = True
    BROWSER_NAV_TIMEOUT_MS: int = 15000
    # A realistic desktop UA so free engines don't serve a bot challenge.
    WEB_USER_AGENT: str = (
        "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
        "(KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36"
    )
    # Cap scraped page text fed into the agent's context (token budget).
    WEB_SCRAPE_MAX_CHARS: int = 6000
    # Below this confidence a world-post is never auto-published (stays pending).
    POST_CONFIDENCE_THRESHOLD: float = 0.55

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
    # Seed the curated welcome agents (Ada/Bram/Cara) at startup. On in prod/dev;
    # tests that need a controlled network set this false.
    SEED_PERSONAS_ON_STARTUP: bool = True

    # Force-stub override. Defaults to FALSE so a production deploy that
    # provisions GEMINI_API_KEY / Google creds goes live automatically —
    # operators no longer have to remember a second "USE_STUBS=false" var.
    # Each service ALSO independently falls back to stub when ITS OWN key is
    # absent (see gemini.py / google_auth.py), so an unset key never crashes.
    # Local dev / tests opt into full stub mode by setting USE_STUBS=true.
    USE_STUBS: bool = False

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

        # Auto-pick a cross-site-compatible cookie policy when the frontend and
        # backend live on different sites (Vercel ↔ Render). Browsers drop a
        # SameSite=Lax cookie on cross-site fetch, which silently breaks the
        # /auth/refresh round-trip and forces re-login every 15 minutes.
        if self._is_cross_site() and (self.COOKIE_SAMESITE or "lax").lower() != "none":
            self.COOKIE_SAMESITE = "none"
            self.COOKIE_SECURE = True
        return self

    def _is_cross_site(self) -> bool:
        try:
            from urllib.parse import urlparse

            fe = urlparse(self.FRONTEND_URL or "").hostname or ""
            be = urlparse(self.AXOLOT_BACKEND_URL or "").hostname or ""
            if not fe or not be:
                return False
            # Same registrable host → same-site. Localhost stays same-site.
            return fe.split(".")[-2:] != be.split(".")[-2:]
        except Exception:  # noqa: BLE001
            return False

    def is_production(self) -> bool:
        """Heuristic: any non-localhost backend URL is treated as production."""
        try:
            from urllib.parse import urlparse

            host = (urlparse(self.AXOLOT_BACKEND_URL or "").hostname or "").lower()
            return host not in {"", "localhost", "127.0.0.1", "0.0.0.0"}
        except Exception:  # noqa: BLE001
            return False


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
