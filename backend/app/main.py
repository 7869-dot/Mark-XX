from contextlib import asynccontextmanager
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.exceptions import HTTPException, RequestValidationError
from apscheduler.schedulers.background import BackgroundScheduler
from slowapi.errors import RateLimitExceeded

from app.core.config import settings
from app.core.db import Base, engine
from app.core.logging import configure_logging, get_logger, log_event
from app.core.ratelimit import limiter, rate_limit_handler
from app.api import (
    auth, agent, tasks, network, memory, system, integrations, social,
    onboarding, schedule, marketplace, agents, email_intel, a2a_inbox,
    personality, debug, ghost, users, posts, notifications_api, invites,
    world, collab, jarvis,
)
from app.api.envelope import envelope
from app.scheduler.jobs import register_jobs

# Import models so Base.metadata is populated before create_all.
from app import models  # noqa: F401

configure_logging()
logger = get_logger("axolot.app")

scheduler = BackgroundScheduler(
    timezone=settings.SCHEDULER_TIMEZONE,
    job_defaults={"misfire_grace_time": 300, "coalesce": True, "max_instances": 1},
)


def _startup_self_check() -> None:
    """Loudly warn if running in production-like environment with insecure defaults.
    Don't crash — Render rolls deploys back on non-zero exits, and we want the
    operator to see the warning in logs and fix it next deploy.
    """
    if not settings.is_production():
        return
    issues: list[str] = []
    if settings.JWT_SECRET in {"dev-jwt-secret-change-me", ""} and not settings.SECRET_KEY:
        issues.append("SECRET_KEY (or JWT_SECRET) is unset — sessions can be forged")
    if not settings.TOKEN_ENC_KEY and not settings.ENCRYPTION_KEY:
        issues.append("ENCRYPTION_KEY is unset — Google tokens use a derived dev key")
    if settings.USE_STUBS:
        issues.append(
            "USE_STUBS=true in production — chat will fall back to the stub "
            "tool router and skip real Gemini. Set USE_STUBS=false on Render."
        )
    if not settings.GEMINI_API_KEY:
        issues.append(
            "GEMINI_API_KEY unset — chat is locked to the stub router. "
            "Set the env var and redeploy."
        )
    if not settings.GOOGLE_CLIENT_ID or not settings.GOOGLE_CLIENT_SECRET:
        issues.append("GOOGLE_CLIENT_ID/SECRET unset — real Google sign-in disabled")
    for msg in issues:
        log_event(logger, "startup_warning", issue=msg)


@asynccontextmanager
async def lifespan(app: FastAPI):
    _startup_self_check()
    Base.metadata.create_all(bind=engine)
    # Add columns/indexes that postdate create_all (Section 8 + Phase 3 columns,
    # Phase 8 scale indexes). Idempotent.
    from app.core.schema_sync import run_schema_sync
    run_schema_sync(engine)
    # One-time idempotent cut-over of legacy social_graph -> agent_connections.
    from app.core.db import SessionLocal
    from app.services.profile_sync import migrate_social_graph_to_connections

    _db = SessionLocal()
    try:
        migrate_social_graph_to_connections(_db)
    except Exception as exc:  # noqa: BLE001
        log_event(logger, "social_graph_migration_failed", error=str(exc))
    finally:
        _db.close()

    # Seed marketplace templates — idempotent, only inserts missing ones.
    from app.services.marketplace import seed_templates

    _db = SessionLocal()
    try:
        seed_templates(_db)
    except Exception as exc:  # noqa: BLE001
        log_event(logger, "marketplace_seed_failed", error=str(exc))
    finally:
        _db.close()

    # Curated welcome agents (Ada/Bram/Cara) — keep the network + new-user feed
    # alive. Idempotent; best-effort so a generation hiccup never blocks boot.
    if settings.SEED_PERSONAS_ON_STARTUP:
        from app.services.seed_personas import seed_persona_agents

        _db = SessionLocal()
        try:
            seed_persona_agents(_db)
        except Exception as exc:  # noqa: BLE001
            log_event(logger, "seed_personas_failed", error=str(exc))
        finally:
            _db.close()

    # Boot-time diagnostics — fail loudly here, not silently at runtime.
    # Bug 2: validate configured Gemini model names (404s show at boot).
    try:
        from app.services import llm_gateway

        llm_gateway.validate_models()
    except Exception as exc:  # noqa: BLE001
        log_event(logger, "llm_model_validation_error", error=str(exc))
    # Bug 1: report whether the local headless browser (Playwright + Chromium)
    # is usable, so a missing Render Chromium install is obvious on boot.
    try:
        from app.services.local_browser import browser_available

        usable = browser_available()
        log_event(logger, "browser_availability", playwright_usable=usable)
        if not usable:
            log_event(logger, "startup_warning",
                      issue="Playwright/Chromium not usable — web search falls back "
                            "to httpx (DDG Lite) then SerpAPI. Run "
                            "`python -m playwright install chromium --with-deps` in the build.")
    except Exception as exc:  # noqa: BLE001
        log_event(logger, "browser_availability_check_failed", error=str(exc))

    register_jobs(scheduler)
    scheduler.start()
    log_event(
        logger, "startup",
        jobs=[j.id for j in scheduler.get_jobs()],
        cors_origins=_cors_origins,
        cookie_samesite=settings.COOKIE_SAMESITE,
        cookie_secure=settings.COOKIE_SECURE,
        stub_mode=settings.USE_STUBS,
        production=settings.is_production(),
    )
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="Axolot API", version="0.2.0", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

# Explicit origins — wildcard breaks Google OAuth credentialed requests.
_cors_origins = sorted({
    settings.FRONTEND_URL,
    "https://axolot.vercel.app",
    "http://localhost:5173",
    "http://127.0.0.1:5173",
})
# Vercel preview deploys land on axolot-git-<branch>-<scope>.vercel.app and
# axolot-<hash>-<scope>.vercel.app. Allow them via regex so stakeholder demos
# aren't blocked by CORS without opening up to every *.vercel.app site.
_cors_origin_regex = r"^https://axolot(-git)?-[a-z0-9-]+\.vercel\.app$"
app.add_middleware(
    CORSMiddleware,
    allow_origins=_cors_origins,
    allow_origin_regex=_cors_origin_regex,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


def _error_body(message: str, code: str) -> dict:
    return {
        "success": False,
        "data": None,
        "error": code,
        "message": message,
        "code": code,
        "meta": {"timestamp": datetime.utcnow().isoformat(), "agent_id": None},
    }


@app.exception_handler(HTTPException)
async def http_exc_handler(request: Request, exc: HTTPException):
    return JSONResponse(
        status_code=exc.status_code,
        content=_error_body(str(exc.detail), f"http_{exc.status_code}"),
    )


@app.exception_handler(RequestValidationError)
async def validation_exc_handler(request: Request, exc: RequestValidationError):
    return JSONResponse(
        status_code=422,
        content=_error_body("Request validation failed", "validation_error"),
    )


@app.exception_handler(Exception)
async def unhandled_exc_handler(request: Request, exc: Exception):
    # Never leak a raw 500 — always a structured 4xx-style envelope.
    log_event(logger, "unhandled_exception", path=str(request.url), error=str(exc))
    return JSONResponse(
        status_code=500, content=_error_body("Internal error", "internal_error")
    )


app.include_router(system.router)
app.include_router(auth.router)
app.include_router(agent.router)
app.include_router(tasks.router)
app.include_router(network.router)
app.include_router(memory.router)
app.include_router(integrations.router)
app.include_router(social.router)
app.include_router(onboarding.router)
app.include_router(schedule.router)
app.include_router(marketplace.router)
app.include_router(agents.router)
app.include_router(email_intel.router)
app.include_router(a2a_inbox.router)
app.include_router(personality.router)
app.include_router(ghost.router)
app.include_router(users.router)
app.include_router(posts.router)
app.include_router(notifications_api.router)
app.include_router(invites.router)
app.include_router(world.router)
app.include_router(collab.router)
app.include_router(jarvis.router)
app.include_router(debug.router)


@app.get("/")
def root():
    return envelope({"name": "Axolot API", "version": "0.2.0"})
