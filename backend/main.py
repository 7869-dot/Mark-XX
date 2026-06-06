"""FastAPI application — chat SSE stream, email confirm, and A2A endpoints."""
import asyncio
import json
import logging
import uuid
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import matchmaker
import orchestrator
from api.a2a import router as a2a_router
from api.auth import router as auth_router
from config import A2A_SCHEDULE_MINUTES
from db import init_db
from tools.email_tools import send_email

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# ── APScheduler singleton guard ────────────────────────────────────────────────
# Prevents double-registration when uvicorn --reload triggers multiple lifespan
# cycles in the same process (rare, but possible in some reload modes).
_scheduler: AsyncIOScheduler | None = None


@asynccontextmanager
async def lifespan(app: FastAPI):
    global _scheduler

    init_db()
    logger.info("Database tables ready")

    if _scheduler is None or not _scheduler.running:
        _scheduler = AsyncIOScheduler()
        _scheduler.add_job(
            matchmaker.run_all,
            "interval",
            minutes=A2A_SCHEDULE_MINUTES,
            id="matchmaker",
            replace_existing=True,
        )
        _scheduler.start()
        logger.info("Matchmaker scheduled every %d minutes", A2A_SCHEDULE_MINUTES)
    else:
        logger.info("Scheduler already running — skipping re-registration")

    yield

    if _scheduler and _scheduler.running:
        _scheduler.shutdown(wait=False)
        _scheduler = None


app = FastAPI(title="Axolotl API", version="2.1.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)   # /auth/login, /auth/callback, /auth/me
app.include_router(a2a_router)    # /agent-card, /briefings, /admin

# In-memory draft store. Replace with Redis for multi-process deployments.
_pending_drafts: dict[str, dict] = {}


# ── Request / Response models ──────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str


class ConfirmEmailRequest(BaseModel):
    draft_id: str
    to:       str
    subject:  str
    body:     str


# ── Chat SSE ───────────────────────────────────────────────────────────────────

@app.post("/chat")
async def chat(req: ChatRequest):
    """SSE streaming endpoint.  Each frame: `data: <json>\\n\\n`"""

    async def event_stream():
        queue: asyncio.Queue[str | None] = asyncio.Queue()

        async def emit(event: dict) -> None:
            if event.get("type") == "email_draft":
                draft_id = str(uuid.uuid4())
                _pending_drafts[draft_id] = event["draft"]
                event = {**event, "draft_id": draft_id}
            await queue.put(f"data: {json.dumps(event)}\n\n")

        async def run() -> None:
            try:
                await orchestrator.run(req.message, emit)
            except Exception as exc:
                await emit({"type": "error", "message": str(exc)})
            finally:
                await queue.put(None)

        asyncio.create_task(run())
        while True:
            item = await queue.get()
            if item is None:
                break
            yield item

    return StreamingResponse(event_stream(), media_type="text/event-stream")


# ── Email confirm ──────────────────────────────────────────────────────────────

@app.post("/confirm-email")
async def confirm_email(req: ConfirmEmailRequest):
    if req.draft_id not in _pending_drafts:
        raise HTTPException(status_code=404, detail="Draft not found or already sent.")
    try:
        result = send_email(req.to, req.subject, req.body)
        _pending_drafts.pop(req.draft_id, None)
        return {"success": True, "message": result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


# ── Health ─────────────────────────────────────────────────────────────────────

@app.get("/health")
async def health():
    return {"status": "ok", "model": "gemini-2.5-flash"}
