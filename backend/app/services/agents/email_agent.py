from app.services.llm_gateway import LLMService
from app.core.config import settings

class EmailAgent:
    def __init__(self):
        self.llm = LLMService(model_name=settings.SUBAGENT_MODEL)

    async def draft_email(self, recipient: str, subject: str, content_goal: str) -> str:
        prompt = f"Draft a professional email to {recipient} regarding '{subject}'. Goal: {content_goal}"
        draft = await self.llm.generate_response(prompt)
        return draft

    async def process_inbox(self, user_token: str) -> str:
        # Placeholder for Gmail API integration
        return "You have 3 new emails. 1 from Haani regarding Axolot updates."
