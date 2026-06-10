from fastapi import APIRouter, Depends, Query
from fastapi.responses import StreamingResponse
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.models import User
from app.services.agents.jarvis import JarvisOrchestrator
from app.services.sse import SSEService
import asyncio

router = APIRouter()

@router.get("/stream")
async def chat_stream(
    query: str = Query(..., min_length=1),
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    orchestrator = JarvisOrchestrator(db)
    
    async def event_generator():
        try:
            async for chunk in orchestrator.chat(current_user.id, query):
                yield await SSEService.format_event(chunk)
                # Small sleep to prevent overwhelming the connection
                await asyncio.sleep(0.01)
            
            # Send completion signal
            yield await SSEService.format_event("[DONE]", event_type="end")
            
        except Exception as e:
            yield await SSEService.format_event(str(e), event_type="error")

    return StreamingResponse(event_generator(), media_type="text/event-stream")
