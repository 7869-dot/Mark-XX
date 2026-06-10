from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.future import select
from app.models.models import UserPersonality
from typing import Optional, Dict, Any

class PersonalityService:
    @staticmethod
    async def get_personality(db: AsyncSession, user_id: str) -> Optional[UserPersonality]:
        result = await db.execute(
            select(UserPersonality).filter(UserPersonality.user_id == user_id)
        )
        return result.scalars().first()

    @staticmethod
    async def update_personality(
        db: AsyncSession, user_id: str, traits: Dict[str, Any] = None, preferences: Dict[str, Any] = None
    ):
        result = await db.execute(
            select(UserPersonality).filter(UserPersonality.user_id == user_id)
        )
        personality = result.scalars().first()

        if not personality:
            personality = UserPersonality(user_id=user_id, traits=traits or {}, preferences=preferences or {})
            db.add(personality)
        else:
            if traits:
                personality.traits = {**personality.traits, **traits}
            if preferences:
                personality.preferences = {**personality.preferences, **preferences}
        
        await db.commit()
        await db.refresh(personality)
        return personality
