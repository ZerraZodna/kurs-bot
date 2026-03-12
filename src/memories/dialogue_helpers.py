"""Memory extraction utilities for dialogue.

This module provides helper functions for memory extraction.
"""

from __future__ import annotations

import re
from src.memories.manager import MemoryManager
from src.memories.constants import MemoryKey


def _normalize_lesson_completed_value(value) -> str | None:
    """Return a normalized lesson id string (1-365) or None for invalid input."""
    try:
        if isinstance(value, int):
            lesson_id = value
        elif isinstance(value, float):
            if not value.is_integer():
                return None
            lesson_id = int(value)
        elif isinstance(value, str):
            raw = value.strip()
            if not raw:
                return None
            if raw.isdigit():
                lesson_id = int(raw)
            else:
                m = re.search(r"\b(?:lesson|leksjon)?\s*(\d{1,3})\b", raw.lower())
                if not m:
                    return None
                lesson_id = int(m.group(1))
        else:
            return None
    except Exception:
        return None

    if 1 <= int(lesson_id) <= 365:
        return str(int(lesson_id))
    return None


def get_user_language(memory_manager: MemoryManager, user_id: int) -> str:
    """Get user's preferred language."""
    memories = memory_manager.get_memory(user_id, MemoryKey.USER_LANGUAGE)
    # Stored values are ISO codes (e.g., 'en', 'no'). Return stored value or 'en'.
    return memories[0].get("value", "en") if memories else "en"

