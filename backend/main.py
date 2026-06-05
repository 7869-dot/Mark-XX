"""FastAPI application — exposes the /chat SSE stream and /confirm-email endpoints."""
import asyncio
import json
import uuid

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import StreamingResponse
from pydantic import BaseModel

import orchestrator
from tools.email_tools import send_email

app = FastAPI(title="Axolotl API", version="1.0.0")

app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://localhost:3000"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# In-memory draft store. Replace with Redis for multi-process deployments.
_pending_drafts: dict[str, dict] = {}


# ── Request / Response models ─────────────────────────────────────────────────

class ChatRequest(BaseModel):
    message: str


class ConfirmEmailRequest(BaseModel):
    draft_id: str
    to: str
    subject: str
    body: str


# ── Endpoints ─────────────────────────────────────────────────────────────────

@app.post("/chat")
async def chat(req: ChatRequest):
    """
    SSE streaming endpoint.  The client reads the response body as a stream of
    newline-delimited `data: <json>\\n\\n` frames.
    """

    async def event_stream():
        queue: asyncio.Queue[str | None] = asyncio.Queue()

        async def emit(event: dict) -> None:
            # Intercept email_draft events to persist the draft and attach an id
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
                await queue.put(None)  # sentinel → close stream

        asyncio.create_task(run())

        while True:
            item = await queue.get()
            if item is None:
                break
            yield item

    return StreamingResponse(event_stream(), media_type="text/event-stream")


@app.post("/confirm-email")
async def confirm_email(req: ConfirmEmailRequest):
    """User approved the draft — actually send the email."""
    if req.draft_id not in _pending_drafts:
        raise HTTPException(status_code=404, detail="Draft not found or already sent.")
    try:
        result = send_email(req.to, req.subject, req.body)
        _pending_drafts.pop(req.draft_id, None)
        return {"success": True, "message": result}
    except Exception as exc:
        raise HTTPException(status_code=500, detail=str(exc))


@app.get("/health")
async def health():
    return {"status": "ok"}
