"""SQLAlchemy engine, session factory, and Base.

Pattern: no migration tool. Tables are created with Base.metadata.create_all()
on application startup (see main.py lifespan). Adding a column = add it here
and delete axolotl.db to let SQLite recreate it, or run ALTER TABLE manually.
"""
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from config import DATABASE_URL

# check_same_thread=False is SQLite-specific; harmless for other dialects.
engine = create_engine(
    DATABASE_URL,
    connect_args={"check_same_thread": False} if DATABASE_URL.startswith("sqlite") else {},
    echo=False,
)

SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()


def get_db():
    """FastAPI dependency — yields a scoped Session, closes on exit."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def init_db() -> None:
    """Create all tables.  Import models first so they register with Base."""
    import models  # noqa: F401 — side-effect: registers all ORM classes
    Base.metadata.create_all(bind=engine)
