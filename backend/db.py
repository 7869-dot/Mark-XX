"""SQLAlchemy engine, session factory, and Base.

Pattern: no migration tool.
• New tables  → add model class, call create_all() on startup (automatic).
• New columns → add to model AND to upgrade_db() below; it runs ALTER TABLE
  with try/except so existing DBs are updated non-destructively.
• If all else fails, delete axolotl.db and restart.
"""
import logging

from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, declarative_base

from config import DATABASE_URL

logger = logging.getLogger(__name__)

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


def _safe_alter(conn, sql: str) -> None:
    """Run an ALTER TABLE and silently ignore 'column already exists' errors."""
    try:
        conn.execute(text(sql))
        conn.commit()
    except Exception:
        pass  # column already present


def upgrade_db() -> None:
    """
    Apply new columns to existing tables without dropping data.
    Called after create_all() on every startup.
    Add a _safe_alter() call here whenever a new nullable column is added to
    an existing model.
    """
    with engine.connect() as conn:
        # Phase 2: Google OAuth fields on users
        _safe_alter(conn, "ALTER TABLE users ADD COLUMN google_sub TEXT")
        _safe_alter(conn, "ALTER TABLE users ADD COLUMN email TEXT")
    logger.debug("upgrade_db complete")


def init_db() -> None:
    """Create all tables then apply column upgrades."""
    import models  # noqa: F401 — registers all ORM classes with Base
    Base.metadata.create_all(bind=engine)
    upgrade_db()
