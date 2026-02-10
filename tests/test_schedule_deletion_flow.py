import pytest

from src.models.database import SessionLocal
from src.services.memory_manager import MemoryManager
from src.services.scheduler import SchedulerService
from src.services.dialogue_engine import DialogueEngine
from tests.utils import make_ready_user


@pytest.mark.asyncio
async def test_list_and_delete_reminders_flow():
    db = SessionLocal()
    try:
        user_id = make_ready_user(db, external_id="test-delete-1", first_name="DelTest")

        # create two daily schedules
        s1 = SchedulerService.create_daily_schedule(user_id=user_id, lesson_id=None, time_str="14:00")
        s2 = SchedulerService.create_daily_schedule(user_id=user_id, lesson_id=None, time_str="09:00")

        dialogue = DialogueEngine(db)

        # List reminders - should include both
        resp = await dialogue.process_message(user_id, "List reminders", db)
        assert "Daily reminder at" in resp
        assert "14:00" in resp
        assert "09:00" in resp

        # Delete reminders -> should ask for confirmation
        resp2 = await dialogue.process_message(user_id, "Delete reminders", db)
        assert "Are you sure" in resp2 or "confirm" in resp2

        # Confirm deletion
        resp3 = await dialogue.process_message(user_id, "yes", db)
        assert "deleted" in resp3.lower() or "i've deleted" in resp3.lower() or "i have deleted" in resp3.lower()

        # Active schedules should be empty
        active = SchedulerService.get_user_schedules(user_id)
        assert active == []

        # Listing now should say none
        resp4 = await dialogue.process_message(user_id, "List reminders", db)
        assert "You don't have any active reminders" in resp4 or "no active reminders" in resp4.lower()

    finally:
        db.close()
