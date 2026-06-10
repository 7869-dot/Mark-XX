from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.models import ConversationSummary
from typing import Optional

class SummarizerService:
    @staticmethod
    async def get_latest_summary(db: AsyncSession, user_id: str) -> Optional[ConversationSummary]:
        result = await db.execute(
            select(ConversationSummary)
            .filter(ConversationSummary.user_id == user_id)
            .order_by(ConversationSummary.created_at.desc())
            .limit(1)
        )
        return result.scalars().first()

    @staticmethod
    async def save_summary(db: AsyncSession, user_id: str, summary_text: str, last_chat_id: int):
        summary = ConversationSummary(
            user_id=user_id,
            summary=summary_text,
            last_chat_id=last_chat_id
        )
        db.add(summary)
        await db.commit()
        await db.refresh(summary)
        return summary
