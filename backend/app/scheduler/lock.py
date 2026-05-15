"""Cooperative DB lock so a scheduled job never runs twice concurrently."""
from contextlib import contextmanager
from datetime import datetime, timedelta

from app.core.db import SessionLocal
from app.models.system import SchedulerLock

STALE_AFTER = timedelta(minutes=30)


@contextmanager
def job_lock(job_id: str):
    """Yield True if the lock was acquired, else False. Always released."""
    db = SessionLocal()
    acquired = False
    try:
        row = db.query(SchedulerLock).filter(SchedulerLock.job_id == job_id).first()
        if row is None:
            row = SchedulerLock(job_id=job_id, locked=True, locked_at=datetime.utcnow())
            db.add(row)
            db.commit()
            acquired = True
        elif not row.locked or (datetime.utcnow() - (row.locked_at or datetime.min)) > STALE_AFTER:
            row.locked = True
            row.locked_at = datetime.utcnow()
            db.commit()
            acquired = True
        if acquired:
            yield True
        else:
            yield False
    finally:
        if acquired:
            row = db.query(SchedulerLock).filter(SchedulerLock.job_id == job_id).first()
            if row:
                row.locked = False
                db.commit()
        db.close()
