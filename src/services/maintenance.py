from __future__ import annotations

import logging
from typing import Optional
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from src.models.database import SessionLocal, MessageLog, Memory
from src.services.memory_manager import MemoryManager

logger = logging.getLogger(__name__)


def purge_archived_memories(days_keep: int = 365, session: Optional[Session] = None) -> int:
    """Purge archived memories older than days_keep. Returns number deleted."""
    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True

    try:
        memory_manager = MemoryManager(session)
        deleted = memory_manager.purge_expired(days_keep=days_keep)
        logger.info("Purged %s archived memories older than %s days", deleted, days_keep)
        return deleted
    finally:
        if close_session:
            session.close()


def purge_expired_ttl_memories(session: Optional[Session] = None) -> int:
    """Delete memories whose TTL has expired. Returns number deleted."""
    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True

    try:
        cutoff = datetime.now(timezone.utc)
        q = session.query(Memory).filter(
            Memory.ttl_expires_at != None,
            Memory.ttl_expires_at < cutoff,
        )
        deleted = q.count()
        q.delete(synchronize_session=False)
        session.commit()
        logger.info("Purged %s memories with expired TTL", deleted)
        return deleted
    finally:
        if close_session:
            session.close()


def purge_expired_batch_locks() -> None:
    """Remove expired batch locks from the database."""
    try:
        def _do_purge():
            db = SessionLocal()
            try:
                from src.models.database import BatchLock

                deleted = db.query(BatchLock).filter(
                    BatchLock.expires_at < datetime.now(timezone.utc)
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
    close_session = False
    if session is None:
        session = SessionLocal()
        close_session = True

    try:
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_keep)
        q = session.query(MessageLog).filter(MessageLog.created_at < cutoff)
        deleted = q.count()
        q.delete(synchronize_session=False)
        session.commit()
        logger.info("Purged %s MessageLog rows older than %s days", deleted, days_keep)
        return deleted
    finally:
        if close_session:
            session.close()


def run_daily_maintenance(days_keep: int = 365) -> None:
    """Run daily maintenance tasks for memory retention."""
    start = datetime.now(timezone.utc)
    deleted = purge_archived_memories(days_keep=days_keep)
    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
    logger.info("Daily maintenance complete. Deleted=%s, elapsed=%.2fs", deleted, elapsed)


def run_gdpr_retention() -> None:
    """Run GDPR retention tasks (TTL memory cleanup)."""
    start = datetime.now(timezone.utc)
    deleted_ttl = purge_expired_ttl_memories()
    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
    logger.info("GDPR retention complete. TTL deleted=%s, elapsed=%.2fs", deleted_ttl, elapsed)
