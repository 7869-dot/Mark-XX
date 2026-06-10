from sqlalchemy.ext.asyncio import AsyncSession
from app.services.memory.chat_history import ChatHistoryService
from app.services.memory.summarizer import SummarizerService
from app.services.memory.personality import PersonalityService
from app.core.config import settings

class ContextBuilder:
    @staticmethod
    async def build_context(db: AsyncSession, user_id: str, current_query: str) -> str:
        # 1. Get recent chat history
        history = await ChatHistoryService.get_recent_history(db, user_id, limit=5)
        
        # 2. Get latest summary
        summary = await SummarizerService.get_latest_summary(db, user_id)
        
        # 3. Get user personality
        personality = await PersonalityService.get_personality(db, user_id)
        
        # Build the final prompt
        agent_name = "Batcomputer" if settings.AGENT_NAME == "Jarvis" else settings.AGENT_NAME
        prompt = (
            f"System: You are the {agent_name}, a military-grade tactical mainframe AI designed by Wayne Enterprises. "
            "Adopt a highly secure, high-tech tactical tone. Refer to the user as 'Sir', 'Master Wayne', or 'Authorized Entity'. "
            "Provide telemetry, data readouts, and tactical advice. Be precise, gritty, and direct, matching the theme of The Dark Knight Rises.\n"
        )
        
        if personality:
            prompt += f"User Traits: {personality.traits}\n"
            prompt += f"User Preferences: {personality.preferences}\n"
            
        if summary:
            prompt += f"Previous Conversation Summary: {summary.summary}\n"
            
        prompt += "Recent Conversation:\n"
        for msg in history:
            prompt += f"{msg.role.capitalize()}: {msg.content}\n"
            
        prompt += f"User: {current_query}\n"
        prompt += f"{agent_name}:"
        
        return prompt
