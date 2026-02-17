import pytest
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.database import SessionLocal, Memory, Schedule
from tests.utils import create_test_user
from src.services.dialogue_engine import DialogueEngine
from src.memories import MemoryManager
from src.scheduler.lesson_state import get_current_lesson


@pytest.mark.asyncio
async def test_onboarding_lesson_reply_defers_to_onboarding():
    """When onboarding asks lesson-status and user replies 'I am on lesson 8',
    the flow should persist the lesson, create the default schedule, and
    return the onboarding-complete message instead of delivering the lesson."""
    db = SessionLocal()
    user_id = create_test_user(db, "test_onboarding_defers", first_name="Carol")

    # Pre-store consent and commitment so onboarding proceeds to lesson_status
    mm = MemoryManager(db)
    mm.store_memory(user_id, "data_consent", "granted", category="profile", source="test")
    mm.store_memory(user_id, "acim_commitment", "committed to ACIM lessons", category="goals", source="test")

    dialogue = DialogueEngine(db)

    # Start onboarding (bot will ask lesson status)
    resp = await dialogue.process_message(user_id, "Hi", db)
    assert resp is not None

    # User replies with an explicit lesson number
    resp2 = await dialogue.process_message(user_id, "I am on lesson 8", db)
    assert resp2 is not None

    # Response should be the onboarding-complete style message (mentions daily reminders)
    assert "Daily reminders" in resp2 or "Daily reminders" in resp2

    # Memory should have recorded current_lesson=8
    cur = get_current_lesson(mm, user_id)
    assert cur == 8, f"Expected current_lesson=8, got {cur}"

    # Simulate onboarding completion side-effect which creates the schedule
    _ = dialogue.onboarding.get_onboarding_complete_message(user_id)
    schedules = db.query(Schedule).filter_by(user_id=user_id).all()
    assert any(s.schedule_type.startswith("daily") and s.is_active for s in schedules), f"Expected active daily schedule, got {schedules}"

    db.close()
