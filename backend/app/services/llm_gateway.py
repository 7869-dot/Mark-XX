import google.generativeai as genai
from app.core.config import settings
from typing import AsyncGenerator, List, Dict, Any

class LLMService:
    def __init__(self, model_name: str = settings.ORCHESTRATOR_MODEL):
        genai.configure(api_key=settings.GEMINI_API_KEY)
        self.model = genai.GenerativeModel(model_name)

    async def generate_response(self, prompt: str) -> str:
        response = await self.model.generate_content_async(prompt)
        return response.text

    async def stream_response(self, prompt: str) -> AsyncGenerator[str, None]:
        response = await self.model.generate_content_async(prompt, stream=True)
        async for chunk in response:
            if chunk.text:
                yield chunk.text

    async def generate_with_tools(self, prompt: str, tools: List[Dict[str, Any]]) -> Any:
        # Placeholder for tool-calling implementation if needed later
        # Gemini handles tools via function declarations
        pass
