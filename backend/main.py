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
from config import A2A_SCHEDULE_MINUTES
from db import init_db
from tools.email_tools import send_email

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


# ── Lifespan ───────────────────────────────────────────────────────────────────

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Create DB tables on startup (no-op if they already exist)
    init_db()
    logger.info("Database tables ready")

    # Start background matchmaking scheduler
    scheduler = AsyncIOScheduler()
    scheduler.add_job(
        matchmaker.run_all,
        "interval",
        minutes=A2A_SCHEDULE_MINUTES,
        id="matchmaker",
        replace_existing=True,
    )
    scheduler.start()
    logger.info("Matchmaker scheduled every %d minutes", A2A_SCHEDULE_MINUTES)

    yield

    scheduler.shutdown(wait=False)


app = FastAPI(title="Axolotl API", version="2.0.0", lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount the A2A router (agent cards, briefings, admin)
app.include_router(a2a_router)

# In-memory draft store (email approval). Replace with Redis for multi-process.
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
    """SSE streaming endpoint. Each frame: `data: <json>\\n\\n`"""

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
    return {"status": "ok"}
