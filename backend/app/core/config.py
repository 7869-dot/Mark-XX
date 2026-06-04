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
    # Single authoritative model for the whole app (product-owner mandate).
    # Every task tier (light/heavy/ultra) resolves to this one primary model.
    # NOTE: "gemini-3.1-flash" does NOT exist on the API and 404s every call.
    # The correct id is "gemini-3.5-flash" (cheaper light work may use
    # "gemini-3.1-flash-lite"). Do not reintroduce a non-existent id here.
    LLM_MODEL: str = "gemini-3.5-flash"

    # ── Tiered models (mixture by task) ──────────────────────────────────────
    # The task router (llm_gateway._model_for()) still distinguishes light/heavy/
    # ultra task classes, but per the mandate every tier points at the SAME
    # primary model id. This keeps the routing seam in place (so a future tier
    # split is a one-line config change) while guaranteeing exactly one model is
    # used at runtime. The LLM_FALLBACK_MODELS chain is deliberately retained:
    # it only ever retries *real* Gemini models on a hard error (e.g. a 404 on a
    # renamed id) and NEVER returns a faked/canned response, so it protects
    # availability without violating the single-model intent.
    LLM_MODEL_LIGHT: str = "gemini-3.5-flash"
    LLM_MODEL_HEAVY: str = "gemini-3.5-flash"
    LLM_MODEL_ULTRA: str = "gemini-3.5-flash"

    # Fallback chain: DISABLED by mandate. Exactly one model (gemini-3.5-flash)
    # is allowed at runtime — no alternative models, no silent substitution. When
    # the primary model errors, llm_gateway raises a hard error that surfaces as
    # an honest "couldn't reach the model" message; it NEVER swaps in another
    # model and NEVER returns a faked/canned response.
    LLM_FALLBACK_MODELS: str = ""

    def model_light(self) -> str:
        return self.LLM_MODEL_LIGHT or self.LLM_MODEL

    def model_heavy(self) -> str:
        return self.LLM_MODEL_HEAVY or self.model_light()

    def model_ultra(self) -> str:
        return self.LLM_MODEL_ULTRA or self.model_heavy()

    def fallback_models(self) -> list[str]:
        return [m.strip() for m in (self.LLM_FALLBACK_MODELS or "").split(",") if m.strip()]
    # OpenAI-compatible endpoint for the "local" provider (vLLM/TGI on RunPod,
    # or the eventual fine-tuned Axolot model behind the same wire format).
    LLM_BASE_URL: str = ""          # e.g. https://<pod>.runpod.net/v1
    LLM_API_KEY: str = ""           # bearer for the local/self-hosted endpoint
    LLM_TIMEOUT_SECONDS: float = 30.0

    # ── Agent web access (Sprint 6) ──────────────────────────────────────────
    # Live web search for the web scout + grounded research. The ONLY backend is
    # the FREE, no-API-key local path: DuckDuckGo Lite over httpx + BeautifulSoup,
    # with a headless-Chromium (Playwright) primary when installed (see
    # services.local_browser). No paid providers (no Tavily, no SerpAPI). With
    # USE_STUBS (dev/tests) search short-circuits to deterministic stubs, so the
    # feature works end-to-end with no external dep and no browser install.
    WEB_FETCH_TIMEOUT_SECONDS: float = 12.0

    # ── Autonomous opportunity scan (token control) ──────────────────────────
    # The web scout runs in the background for onboarded users so Jarvis keeps
    # finding opportunities while the user is offline. These caps are the token
    # budget that stops it burning the LLM endlessly:
    #   COOLDOWN_HOURS      — skip a user scanned within this window (cooldown).
    #   MAX_USERS_PER_RUN   — hard ceiling on scans per sweep (daily budget).
    # The scout already dedupes finds by URL and ranks by relevance, so a scan
    # never re-summarises identical results.
    OPPORTUNITY_SCAN_ENABLED: bool = True
    OPPORTUNITY_SCAN_COOLDOWN_HOURS: float = 6.0
    OPPORTUNITY_SCAN_MAX_USERS_PER_RUN: int = 50

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
