from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.models import ChatHistory
from app.schemas.schemas import ChatMessageCreate
from typing import List

class ChatHistoryService:
    @staticmethod
    async def add_message(db: AsyncSession, message_data: ChatMessageCreate) -> ChatHistory:
        db_message = ChatHistory(**message_data.model_dump())
        db.add(db_message)
        await db.commit()
        await db.refresh(db_message)
        return db_message

    @staticmethod
    async def get_recent_history(db: AsyncSession, user_id: str, limit: int = 10) -> List[ChatHistory]:
        result = await db.execute(
            select(ChatHistory)
            .filter(ChatHistory.user_id == user_id)
            .order_by(ChatHistory.created_at.desc())
            .limit(limit)
        )
        messages = result.scalars().all()
        return list(reversed(messages))
