from __future__ import annotations

import logging
import time
from datetime import timedelta
from typing import Optional

from sqlalchemy.orm import Session

from src.config import settings
from src.core.timezone import utc_now
from src.memories.memory_handler import MemoryHandler
from src.models.database import MessageLog, SessionLocal, get_session
from src.scheduler.maintenance import (
    purge_inactive_schedules as _scheduler_purge_inactive_schedules,
)
from src.scheduler.maintenance import (
    purge_job_states as _scheduler_purge_job_states,
)

logger = logging.getLogger(__name__)


def purge_archived_memories(days_keep: int = 365, session: Optional[Session] = None) -> int:
    """Purge archived memories older than days_keep. Returns number deleted."""
    with get_session(session) as s:
        cutoff = utc_now() - timedelta(days=days_keep)
        deleted = MemoryHandler(s).purge_archived_before(cutoff=cutoff)
        logger.info("Purged %s archived memories older than %s days", deleted, days_keep)
        return deleted


def purge_expired_ttl_memories(session: Optional[Session] = None) -> int:
    """Delete memories whose TTL has expired. Returns number deleted."""
    with get_session(session) as s:
        cutoff = utc_now()
        deleted = MemoryHandler(s).purge_expired_ttl_before(cutoff=cutoff)
        logger.info("Purged %s memories with expired TTL", deleted)
        return deleted


def purge_expired_batch_locks() -> None:
    """Remove expired batch locks from the database."""
    try:
        def _do_purge():
            db = SessionLocal()
            try:
                from src.models.database import BatchLock

                deleted = db.query(BatchLock).filter(
                    BatchLock.expires_at < utc_now()
                ).delete(synchronize_session=False)
                if deleted:
                    logger.info("Purged %s expired batch locks", deleted)
                db.commit()
            finally:
                db.close()

        _do_purge()
    except Exception as e:
        logger.warning("Batch lock purge error: %s", e)


def purge_message_logs(days_keep: int = 30, session: Optional[Session] = None) -> int:
    """Delete message logs older than days_keep. Returns number deleted."""
    with get_session(session) as s:
        cutoff = utc_now() - timedelta(days=days_keep)
        q = s.query(MessageLog).filter(MessageLog.created_at < cutoff)
        deleted = q.count()
        q.delete(synchronize_session=False)
        s.commit()
        logger.info("Purged %s MessageLog rows older than %s days", deleted, days_keep)
        return deleted


def purge_inactive_schedules(days_keep: int = 7, session: Optional[Session] = None) -> int:
    """Compatibility wrapper for scheduler-owned purge helper."""
    return _scheduler_purge_inactive_schedules(days_keep=days_keep, session=session)


def purge_job_states(days_keep: int = 30, session: Optional[Session] = None) -> int:
    """Compatibility wrapper for scheduler-owned purge helper."""
    return _scheduler_purge_job_states(days_keep=days_keep, session=session)


def run_daily_maintenance(days_keep: int = 365) -> None:
    """Run daily maintenance tasks for memory retention."""
    start = utc_now()
    # Purge archived memories (long retention by default)
    deleted_memories = purge_archived_memories(days_keep=days_keep)
    # Purge message logs older than 30 days
    deleted_logs = purge_message_logs(days_keep=30)
    # Purge inactive schedules older than 7 days
    deleted_schedules = purge_inactive_schedules(days_keep=7)
    # Purge old job state keys older than 30 days
    deleted_job_states = purge_job_states(days_keep=30)

    elapsed = (utc_now() - start).total_seconds()
    total_deleted = sum([deleted_memories, deleted_logs, deleted_schedules, deleted_job_states])
    logger.info(
        "Daily maintenance complete. Deleted(total)=%s (memories=%s, logs=%s, schedules=%s, job_states=%s), elapsed=%.2fs",
        total_deleted,
        deleted_memories,
        deleted_logs,
        deleted_schedules,
        deleted_job_states,
        elapsed,
    )


def run_gdpr_retention() -> None:
    """Run GDPR retention tasks (TTL memory cleanup)."""
    start = utc_now()
    deleted_ttl = purge_expired_ttl_memories()
    elapsed = (utc_now() - start).total_seconds()
    logger.info("GDPR retention complete. TTL deleted=%s, elapsed=%.2fs", deleted_ttl, elapsed)


def nightly_memory_purge(days_keep: int = settings.MEMORY_ARCHIVE_RETENTION_DAYS, hour_utc: int = 2):
    """Run maintenance at fixed UTC hour (02:00 AM). Skip first run on startup."""
    first_run = True
    while True:
        try:
            now = utc_now()
            next_run = now.replace(hour=hour_utc, minute=0, second=0, microsecond=0)
            if next_run <= now:
                next_run += timedelta(days=1)
            
            # Skip purge on first startup to avoid conflicts with normal operations
            if not first_run:
                sleep_seconds = (next_run - now).total_seconds()
                time.sleep(sleep_seconds)
                perform_maintenance(days_keep=days_keep)
            else:
                # First run: just schedule for next maintenance window
                sleep_seconds = (next_run - now).total_seconds()
                print(f"[purge] Scheduled nightly maintenance at {next_run.isoformat()}")
                time.sleep(sleep_seconds)
            
            first_run = False
        except Exception as e:
            print(f"[purge error] {e}")
            time.sleep(60)


def perform_maintenance(days_keep: int = settings.MEMORY_ARCHIVE_RETENTION_DAYS) -> None:
    """Run the standard maintenance bundle: daily maintenance, GDPR retention and batch lock purge.

    This provides a single entrypoint for scheduled and opportunistic invocations.
    """
    start = utc_now()
    run_daily_maintenance(days_keep=days_keep)
    run_gdpr_retention()
    purge_expired_batch_locks()
    elapsed = (utc_now() - start).total_seconds()
    logger.info("Performed bundled maintenance. elapsed=%.2fs", elapsed)
