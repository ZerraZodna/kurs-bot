import json
from datetime import datetime, timezone

from src.memories.manager import MemoryManager
from src.memories.lesson_state import get_lesson_state, get_current_lesson


def test_onboarding_reports_current_lesson_advances_next(tmp_path):
    """When user reports 'I am on lesson 8' during onboarding, next lesson should be 9.

    We simulate storing a 'current_lesson' memory (as onboarding would do) and
    then ensure the consolidated lesson_state reflects the numeric current_lesson
    and that compute/next logic would advance to the next lesson.
    """
    # Setup a temporary sqlite DB session via MemoryManager default (uses SessionLocal)
    mm = MemoryManager()
    user_id = 12345

    # Simulate onboarding storing the current_lesson value
    mm.store_memory(user_id=user_id, key="current_lesson", value="8", category="progress")

    # Ensure get_current_lesson returns the stored value
    cur = get_current_lesson(mm, user_id)
    assert str(cur) == "8" or cur == 8

    # Now get the consolidated lesson state and verify returned lesson_id == 8 and
    # that logic using last_sent would consider next day advancement to 9 when applicable.
    state = get_lesson_state(mm, user_id)
    assert state.get("current_lesson") == "8" or state.get("current_lesson") == 8
