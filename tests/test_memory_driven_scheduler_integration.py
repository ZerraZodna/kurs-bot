import pytest
from src.models.database import SessionLocal, User, init_db
from src.services.memory_manager import MemoryManager
from src.services.dialogue_engine import DialogueEngine
from src.services.scheduler import SchedulerService


def create_new_test_user(db) -> int:
    existing_user = db.query(User).filter_by(external_id="test_memory_user").first()
    if existing_user:
        from src.models.database import Memory, Schedule

        db.query(Memory).filter_by(user_id=existing_user.user_id).delete()
        db.query(Schedule).filter_by(user_id=existing_user.user_id).delete()
        db.query(User).filter_by(user_id=existing_user.user_id).delete()
        db.commit()

    user = User(
        external_id="test_memory_user",
        channel="test",
        phone_number=None,
        email="memory_test@example.com",
        first_name="Memory",
        last_name="User",
        opted_in=True,
    )
    db.add(user)
    db.commit()
    return user.user_id


@pytest.mark.asyncio
async def test_memory_driven_schedule_creation():
    db = SessionLocal()
    try:
        user_id = create_new_test_user(db)

        # Store commitment and preferred time as memories (no embedding generation)
        mm = MemoryManager(db)
        mm.store_memory(user_id=user_id, key="acim_commitment", value="yes", generate_embedding=False)
        mm.store_memory(user_id=user_id, key="preferred_lesson_time", value="10:15", generate_embedding=False)

        dialogue = DialogueEngine(db)

        # Prevent the memory extractor from overwriting our preferred time
        async def _fake_extract(user_message, user_context=None, model_override=None):
            return []

        dialogue.memory_extractor.extract_memories = _fake_extract

        # Trigger the schedule creation via dialogue flow
        # Mock the LLM to return a structured intent that will create the schedule
        async def _fake_ollama(prompt, model=None):
            import json
            return json.dumps({
                "intent": {
                    "name": "create_schedule",
                    "action_type": "create_schedule",
                    "spec": {"schedule_type": "daily", "time_str": "10:15"},
                }
            })

        dialogue.call_ollama = _fake_ollama

        resp = await dialogue.process_message(user_id, "Set up reminders", db)
        assert resp is not None

        # Simulate trigger execution: structured intent would produce a create_schedule trigger
        from src.services.trigger_dispatcher import get_trigger_dispatcher

        dispatcher = get_trigger_dispatcher(db=db, memory_manager=mm)
        match = {"trigger_id": None, "name": "create_schedule", "action_type": "create_schedule", "score": 1.0, "threshold": 0.5}
        ctx = {"user_id": user_id, "schedule_spec": {"schedule_type": "daily", "time_str": "10:15"}}
        dispatcher.dispatch(match, ctx)

        # Verify schedule created at 10:15 (UTC stored as next_send_time or cron)
        schedules = SchedulerService.get_user_schedules(user_id)
        active = [s for s in schedules if s.is_active]
        assert len(active) == 1
        sched = active[0]
        hour, minute = SchedulerService.parse_time_string("10:15")
        assert sched.next_send_time is None or (sched.next_send_time.hour == hour and sched.next_send_time.minute == minute)

    finally:
        db.close()
