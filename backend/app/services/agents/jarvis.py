from sqlalchemy.ext.asyncio import AsyncSession
from app.services.llm_gateway import LLMService
from app.services.memory.context_builder import ContextBuilder
from app.services.memory.chat_history import ChatHistoryService
from app.schemas.schemas import ChatMessageCreate
from typing import AsyncGenerator

class JarvisOrchestrator:
    def __init__(self, db: AsyncSession):
        self.db = db
        self.llm = LLMService()

    async def chat(self, user_id: str, query: str) -> AsyncGenerator[str, None]:
        # 1. Save user message
        await ChatHistoryService.add_message(
            self.db, 
            ChatMessageCreate(user_id=user_id, role="user", content=query)
        )

        # 2. Build context
        context_prompt = await ContextBuilder.build_context(self.db, user_id, query)

        # 3. Generate and stream response
        full_response = ""
        async for chunk in self.llm.stream_response(context_prompt):
            full_response += chunk
            yield chunk

        # 4. Save assistant response
        await ChatHistoryService.add_message(
            self.db,
            ChatMessageCreate(user_id=user_id, role="assistant", content=full_response)
        )
        
        # 5. Potential background task for memory updates (to be handled by scheduler)
