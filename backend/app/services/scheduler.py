from apscheduler.schedulers.asyncio import AsyncIOScheduler
from sqlalchemy.ext.asyncio import AsyncSession
from app.core.database import SessionLocal
from app.services.memory.summarizer import SummarizerService
from app.services.memory.chat_history import ChatHistoryService
from app.services.llm_gateway import LLMService
import logging

scheduler = AsyncIOScheduler()

async def summarize_all_users():
    """
    Background job to summarize history for all users.
    """
    async with SessionLocal() as db:
        # In a real app, you'd iterate over active users
        # For now, this is a placeholder for the logic
        logging.info("Running background summarization job...")
        
        # Example logic:
        # 1. Fetch users
        # 2. For each user, check if there are new messages since last summary
        # 3. If yes, generate summary using LLM and save
        pass

def start_scheduler():
    scheduler.add_job(summarize_all_users, "interval", hours=1)
    scheduler.start()
    logging.info("APScheduler started.")

def shutdown_scheduler():
    scheduler.shutdown()
    logging.info("APScheduler shut down.")
