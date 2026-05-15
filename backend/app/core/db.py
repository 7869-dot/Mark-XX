from sqlalchemy import create_engine
from sqlalchemy.orm import declarative_base, sessionmaker, Session
from typing import Generator

from app.core.config import settings


is_sqlite = settings.DATABASE_URL.startswith("sqlite")
connect_args = {"check_same_thread": False} if is_sqlite else {}

# Railway PostgreSQL drops idle connections; pool_pre_ping prevents silent
# failures, and a bounded pool keeps us within Railway connection limits.
# SQLite does not support these pool kwargs, so they are applied only for PG.
engine_kwargs: dict = {"connect_args": connect_args, "pool_pre_ping": True}
if not is_sqlite:
    engine_kwargs.update(pool_size=10, max_overflow=20, pool_recycle=1800)

engine = create_engine(settings.DATABASE_URL, **engine_kwargs)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db() -> Generator[Session, None, None]:
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
