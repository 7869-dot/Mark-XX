from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.core.config import settings
from app.api import auth, chat, memory
from app.services.scheduler import start_scheduler, shutdown_scheduler
from app.core.database import engine, Base
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Startup: Create tables if they don't exist
    try:
        logging.info("Connecting to database and verifying/creating tables...")
        import asyncio
        async def create_tables():
            async with engine.begin() as conn:
                await conn.run_sync(Base.metadata.create_all)
        
        # 15 seconds timeout for database setup to prevent hanging deployments
        await asyncio.wait_for(create_tables(), timeout=15.0)
        logging.info("Database setup completed successfully.")
    except asyncio.TimeoutError:
        logging.error("Database initialization timed out after 15 seconds. Proceeding to start web server so deployment doesn't hang.")
    except Exception as e:
        logging.error(f"Database initialization failed: {e}. Proceeding to start web server so deployment doesn't hang.")
    
    # Start background scheduler
    try:
        start_scheduler()
    except Exception as e:
        logging.error(f"Failed to start scheduler: {e}")
    
    yield
    
    # Shutdown: Stop scheduler
    try:
        shutdown_scheduler()
    except Exception as e:
        logging.error(f"Failed to shutdown scheduler: {e}")


app = FastAPI(
    title=settings.PROJECT_NAME,
    version=settings.VERSION,
    lifespan=lifespan
)

# Set all CORS enabled origins
app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "https://axolot.vercel.app",
        "http://localhost:5173",
        "http://127.0.0.1:5173",
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Include Routers
app.include_router(auth.router, prefix="/auth", tags=["Authentication"])
app.include_router(chat.router, prefix="/chat", tags=["Chat"])
app.include_router(memory.router, prefix="/memory", tags=["Memory"])

@app.get("/")
async def root():
    return {"message": f"Welcome to {settings.PROJECT_NAME} API", "status": "online"}
