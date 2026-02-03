from __future__ import annotations

import logging
from typing import Optional
from datetime import datetime, timezone
from sqlalchemy.orm import Session
from src.models.database import SessionLocal
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


def run_daily_maintenance(days_keep: int = 365) -> None:
    """Run daily maintenance tasks for memory retention."""
    start = datetime.now(timezone.utc)
    deleted = purge_archived_memories(days_keep=days_keep)
    elapsed = (datetime.now(timezone.utc) - start).total_seconds()
    logger.info("Daily maintenance complete. Deleted=%s, elapsed=%.2fs", deleted, elapsed)
