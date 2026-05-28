"""Memory helpers for scheduler."""

from sqlalchemy.orm import Session

from src.memories.constants import MemoryKey
from src.memories.manager import MemoryManager
from src.models.schedule import Schedule


def get_schedule_message(db: Session, schedule_id: int) -> str | None:
    """Get the custom message for a schedule from the Schedule model."""
    schedule = db.query(Schedule).filter(Schedule.schedule_id == schedule_id).first()
    return schedule.custom_message if schedule else None


def get_user_language(memory_manager: MemoryManager, user_id: int) -> str:
    memories = memory_manager.get_memory(user_id, MemoryKey.USER_LANGUAGE)
    return memories[0].get("value", "en") if memories else "en"
