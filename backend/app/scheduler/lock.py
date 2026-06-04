"""Cooperative DB lock so a scheduled job runs once per interval even when more
than one process runs its own BackgroundScheduler (multi-worker deploys).

Acquisition is a single ATOMIC conditional UPDATE: only the one caller whose
UPDATE matches the "last run older than the dedup window" predicate wins the
tick. Sibling schedulers that fire the same job within the window get 0 matched
rows and skip. The lock is NOT released at the end of the run — `locked_at`
records the last run, which is what dedupes the next near-simultaneous burst.
"""
from contextlib import contextmanager
from datetime import datetime, timedelta

from app.core.db import SessionLocal
from app.models.system import SchedulerLock

# A job that fired within this window is treated as already-run for this tick.
# Must exceed the worst-case fan-out skew (APScheduler misfire_grace_time is
# 300s) and stay below the shortest job interval (15 min — agent_heartbeat).
DEDUP_WINDOW = timedelta(minutes=10)


@contextmanager
def job_lock(job_id: str):
    """Yield True only for the single caller that wins this tick, else False."""
    db = SessionLocal()
    acquired = False
    try:
        now = datetime.utcnow()
        cutoff = now - DEDUP_WINDOW

        # Ensure the row exists (idempotent). Seed locked_at in the past so the
        # very first tick is immediately acquirable. A concurrent sibling may win
        # the insert race — swallow the IntegrityError and fall through to UPDATE.
        if db.query(SchedulerLock).filter(SchedulerLock.job_id == job_id).first() is None:
            try:
                db.add(SchedulerLock(
                    job_id=job_id, locked=True,
                    locked_at=cutoff - timedelta(seconds=1),
                ))
                db.commit()
            except Exception:  # noqa: BLE001 — lost the insert race; row now exists
                db.rollback()

        # Atomic acquire: exactly one process's UPDATE matches a stale row. Under
        # READ COMMITTED the losers re-evaluate against the just-updated row
        # (locked_at = now, no longer < cutoff) and match 0 rows.
        matched = (
            db.query(SchedulerLock)
            .filter(SchedulerLock.job_id == job_id, SchedulerLock.locked_at < cutoff)
            .update({"locked": True, "locked_at": now}, synchronize_session=False)
        )
        db.commit()
        acquired = matched == 1
        yield acquired
    finally:
        db.close()
