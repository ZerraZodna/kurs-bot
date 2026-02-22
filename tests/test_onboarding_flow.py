import pytest
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.database import SessionLocal, User, Memory, Schedule, init_db
from tests.utils import create_test_user
from src.services.dialogue_engine import DialogueEngine
from src.memories import MemoryManager
from src.memories.lesson_state import get_current_lesson


# Use shared `create_test_user` from tests.utils


@pytest.mark.asyncio
async def test_onboarding_new_user_creates_daily_schedule():
    """New user (with a name) who answers consent+commitment then 'new' should get a daily schedule."""
    db = SessionLocal()
    try:
        user_id = create_test_user(db, "test_onboarding_flow_new_user", first_name="Alice")

        dialogue = DialogueEngine(db)
        mm = MemoryManager(db)

        # Start onboarding
        resp = await dialogue.process_message(user_id, "Hi", db)
        assert resp is not None

        # Grant consent
        resp2 = await dialogue.process_message(user_id, "Yes", db)
        assert resp2 is not None

        # Commit to lessons
        resp3 = await dialogue.process_message(user_id, "Yes", db)
        assert resp3 is not None

        # Indicate new user so lesson 1 is delivered (this triggers completion + schedule creation)
        resp4 = await dialogue.process_message(user_id, "new", db)
        assert resp4 is not None

        # Simulate final onboarding completion step which creates the auto schedule
        # (this is normally triggered when a lesson is delivered).
        _ = dialogue.onboarding.get_onboarding_complete_message(user_id)
        schedules = db.query(Schedule).filter_by(user_id=user_id).all()
        assert any(s.schedule_type.startswith("daily") and s.is_active for s in schedules), f"Expected active daily schedule, got {schedules}"

    finally:
        db.close()


@pytest.mark.asyncio
async def test_onboarding_continuing_user_lesson10_sets_memory_and_schedule():
    """A returning user who says 'I am on lesson 10' should have current_lesson stored and receive a daily schedule."""
    db = SessionLocal()
    user_id = create_test_user(db, "test_onboarding_flow_continuing_user", first_name="Bob")

    # Pre-store consent and commitment so onboarding asks about lesson status
    mm = MemoryManager(db)
    mm.store_memory(user_id, "data_consent", "granted", category="profile", source="test")
    mm.store_memory(user_id, "acim_commitment", "committed to ACIM lessons", category="goals", source="test")

    dialogue = DialogueEngine(db)

    # Begin onboarding which should ask lesson status
    resp = await dialogue.process_message(user_id, "Hi", db)
    assert resp is not None

    # User states they are on lesson 10
    resp2 = await dialogue.process_message(user_id, "I am on lesson 10", db)
    assert resp2 is not None

    # Memory should have recorded current_lesson=10
    mm = MemoryManager(db)
    cur = get_current_lesson(mm, user_id)
    assert cur == 10, f"Expected current_lesson=10, got {cur}"

    # Simulate final onboarding completion to create auto schedule
    _ = dialogue.onboarding.get_onboarding_complete_message(user_id)
    schedules = db.query(Schedule).filter_by(user_id=user_id).all()
    assert any(s.schedule_type.startswith("daily") and s.is_active for s in schedules), f"Expected active daily schedule, got {schedules}"

    db.close()
