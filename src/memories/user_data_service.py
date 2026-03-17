"""Shared user-related memory data cleanup helpers."""

from __future__ import annotations

from typing import Dict, List

from sqlalchemy.orm import Session

from src.memories.memory_handler import MemoryHandler
from src.models.database import MessageLog


def delete_user_content_rows(session: Session, user_id: int) -> Dict[str, int]:
    """Delete user content rows tied to memories/messages/schedules.

    Returns deletion metrics. Caller owns outer transaction/commit.
    """
    deleted_memories = MemoryHandler(session).delete_user_memories(user_id=user_id)
    deleted_messages = session.query(MessageLog).filter_by(user_id=user_id).delete(synchronize_session=False)

    # Scheduler helper performs schedule deletion + APScheduler job cleanup.
    from src.scheduler import delete_user_schedules_and_remove_jobs

    deleted_schedule_ids: List[int] = delete_user_schedules_and_remove_jobs(
        user_id=user_id,
        session=session,
    )

    return {
        "deleted_memories": int(deleted_memories or 0),
        "deleted_messages": int(deleted_messages or 0),
        "deleted_schedules": len(deleted_schedule_ids),
    }
