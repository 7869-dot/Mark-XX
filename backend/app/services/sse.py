import json
from typing import AsyncGenerator

class SSEService:
    @staticmethod
    async def format_event(data: str, event_type: str = "message") -> str:
        return f"event: {event_type}\ndata: {json.dumps({'content': data})}\n\n"

    @staticmethod
    async def ping() -> str:
        return "event: ping\ndata: {\"ping\": \"pong\"}\n\n"
