"""Memory helpers for scheduler."""

import json
from datetime import datetime, timezone
from typing import Optional

from src.memories.constants import MemoryCategory, MemoryKey
from src.memories.manager import MemoryManager


def get_schedule_message(memory_manager: MemoryManager, user_id: int, schedule_id: int) -> Optional[str]:
    memories = memory_manager.get_memory(user_id=user_id, key=MemoryKey.SCHEDULE_MESSAGE)
    for memory in memories:
        try:
            data = json.loads(memory.get("value", ""))
            if data.get("schedule_id") == schedule_id:
                return data.get("message")
        except Exception:
            continue
    return None


def get_user_language(memory_manager: MemoryManager, user_id: int) -> str:
    memories = memory_manager.get_memory(user_id, MemoryKey.USER_LANGUAGE)
    return memories[0].get("value", "en") if memories else "en"

