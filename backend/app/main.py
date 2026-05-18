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
from app.api import auth, agent, tasks, network, memory, system
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


@asynccontextmanager
async def lifespan(app: FastAPI):
    Base.metadata.create_all(bind=engine)
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

    register_jobs(scheduler)
    scheduler.start()
    log_event(logger, "startup", jobs=[j.id for j in scheduler.get_jobs()])
    yield
    scheduler.shutdown(wait=False)


app = FastAPI(title="Axolot API", version="0.2.0", lifespan=lifespan)

app.state.limiter = limiter
app.add_exception_handler(RateLimitExceeded, rate_limit_handler)

# Explicit origins — wildcard breaks Google OAuth credentialed requests.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.FRONTEND_URL, "http://localhost:5173", "http://127.0.0.1:5173"],
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


@app.get("/")
def root():
    return envelope({"name": "Axolot API", "version": "0.2.0"})
