import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, Boolean

from app.core.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class RefreshToken(Base):
    """Tracks issued refresh tokens so rotation can invalidate the prior one.

    Prevents the JWT refresh race: once a refresh token is used it is marked
    used=True and can never be redeemed again.
    """

    __tablename__ = "refresh_tokens"

    id = Column(String, primary_key=True, default=_uuid)
    user_id = Column(String, nullable=False, index=True)
    jti = Column(String, unique=True, nullable=False, index=True)
    used = Column(Boolean, default=False, nullable=False)
    created_at = Column(DateTime, default=datetime.utcnow)
    used_at = Column(DateTime, nullable=True)


class SchedulerLock(Base):
    """Cooperative lock so a job never runs twice concurrently (multi-worker safe)."""

    __tablename__ = "scheduler_locks"

    job_id = Column(String, primary_key=True)
    locked_at = Column(DateTime, default=datetime.utcnow)
    locked = Column(Boolean, default=False, nullable=False)
