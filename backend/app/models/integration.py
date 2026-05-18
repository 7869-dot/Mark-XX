import uuid
from datetime import datetime
from sqlalchemy import Column, String, DateTime, ForeignKey, Integer, Boolean

from app.core.db import Base


def _uuid() -> str:
    return str(uuid.uuid4())


class WatchedThread(Base):
    """A Gmail thread an agent is monitoring for new replies.

    We store ONLY the thread id + bookkeeping — never email content.
    """

    __tablename__ = "watched_threads"

    id = Column(String, primary_key=True, default=_uuid)
    agent_id = Column(String, ForeignKey("agents.id"), nullable=False, index=True)
    user_id = Column(String, ForeignKey("users.id"), nullable=False, index=True)
    thread_id = Column(String, nullable=False, index=True)
    subject = Column(String, default="")
    last_checked_at = Column(DateTime, default=datetime.utcnow)
    last_message_id = Column(String, nullable=True)
    check_interval_hours = Column(Integer, default=4)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime, default=datetime.utcnow)
