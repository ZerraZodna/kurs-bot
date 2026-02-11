import json
from datetime import datetime, timezone, timedelta

from src.models.database import SessionLocal, User, init_db, Memory, Schedule
from src.services.memory_manager import MemoryManager
from src.services.trigger_dispatcher import get_trigger_dispatcher


def test_remind_me_creates_one_time_with_correct_message():
    db = SessionLocal()
    try:

        from tests.utils import make_ready_user

        # Create a ready user with onboarding completed
        user_id = make_ready_user(db, external_id="remind_test_user", first_name="Remind")

        # Build a schedule_spec like an assistant intent would provide
        run_at = (datetime.now(timezone.utc) + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
        spec = {
            "schedule_type": "one_time_reminder",
            "run_at": run_at.isoformat(),
            "message": "Remind me to go out with the garbage at 12:00",
        }

        # Dispatch create_schedule with schedule_spec
        dispatcher = get_trigger_dispatcher(db, MemoryManager(db))
        match = {"trigger_id": None, "name": "create_schedule", "action_type": "create_schedule", "score": 1.0, "threshold": 0.8}
        res = dispatcher.dispatch(match, {"user_id": user_id, "schedule_spec": spec})
        assert res.get("ok") is True

        # Verify a one-time schedule row exists
        schedules = db.query(Schedule).filter_by(user_id=user_id).all()
        one_time = [s for s in schedules if s.schedule_type and s.schedule_type.startswith("one_time")]
        assert len(one_time) == 1

        # Verify the stored schedule message in memory matches the provided text
        mm = MemoryManager(db)
        memories = mm.get_memory(user_id=user_id, key="schedule_message")
        assert memories and len(memories) >= 1
        payload = json.loads(memories[-1].get("value"))
        assert payload.get("message") == spec["message"]

    finally:
        db.close()
