from fastapi import APIRouter, Depends
from sqlalchemy.ext.asyncio import AsyncSession
from app.api.auth import get_current_user
from app.core.database import get_db
from app.models.models import User
from app.services.memory.chat_history import ChatHistoryService
from app.services.memory.summarizer import SummarizerService
from app.services.memory.personality import PersonalityService
from app.schemas.schemas import ChatMessage, Summary, Personality
from typing import List

router = APIRouter()

@router.get("/history", response_model=List[ChatMessage])
async def get_history(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await ChatHistoryService.get_recent_history(db, current_user.id)

@router.get("/summary", response_model=Summary)
async def get_summary(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    summary = await SummarizerService.get_latest_summary(db, current_user.id)
    return summary

@router.get("/personality", response_model=Personality)
async def get_personality(
    current_user: User = Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    return await PersonalityService.get_personality(db, current_user.id)
