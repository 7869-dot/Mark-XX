from google import genai
from app.core.config import settings
from typing import AsyncGenerator, List, Dict, Any

class LLMService:
    def __init__(self, model_name: str = settings.ORCHESTRATOR_MODEL):
        self.client = genai.Client(api_key=settings.GEMINI_API_KEY)
        self.model_name = model_name

    async def generate_response(self, prompt: str) -> str:
        response = await self.client.aio.models.generate_content(
            model=self.model_name,
            contents=prompt
        )
        return response.text

    async def stream_response(self, prompt: str) -> AsyncGenerator[str, None]:
        async for chunk in self.client.aio.models.generate_content_stream(
            model=self.model_name,
            contents=prompt
        ):
            if chunk.text:
                yield chunk.text

    async def generate_with_tools(self, prompt: str, tools: List[Dict[str, Any]]) -> Any:
        # Placeholder for tool-calling implementation if needed later
        # Gemini handles tools via function declarations
        pass
