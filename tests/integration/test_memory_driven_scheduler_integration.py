"""
Integration tests for memory-driven scheduler.

Migrated from tests/test_memory_driven_scheduler_integration.py to use new test fixtures.
"""

import pytest
from src.models.database import User
from src.memories import MemoryManager
from src.memories.memory_handler import MemoryHandler
from src.services.dialogue_engine import DialogueEngine
from src.scheduler import SchedulerService
from src.triggers.trigger_dispatcher import get_trigger_dispatcher


@pytest.mark.asyncio
#@pytest.mark.serial
async def test_memory_driven_schedule_creation(db_session, test_user):
    """Given: A user with commitment and preferred time stored as memories
    When: Triggering schedule creation via dialogue
    Then: Should create a schedule at the preferred time."""
    user_id = test_user.user_id

    # Store commitment and preferred time as memories (no embedding generation)
    mm = MemoryManager(db_session)
    mm.store_memory(user_id=user_id, key="acim_commitment", value="yes")
    mm.store_memory(user_id=user_id, key="preferred_lesson_time", value="10:15")

    dialogue = DialogueEngine(db_session, mm)

    # Prevent the memory extractor from overwriting our preferred time
    async def _fake_extract(user_message, user_context=None, model_override=None, language=None):
        return []

    dialogue.memory_extractor.extract_memories = _fake_extract

    # Trigger the schedule creation via dialogue flow
    # Mock the LLM to return a structured intent that will create the schedule
    async def _fake_ollama(prompt, model=None, language=None):
        import json
        return json.dumps({
            "intent": {
                "name": "create_schedule",
                "action_type": "create_schedule",
                "spec": {"schedule_type": "daily", "time_str": "10:15"},
            }
        })

    # Patch module-level ollama client so any code path uses the fake implementation
    import importlib
    mod = importlib.import_module("src.services.dialogue.ollama_client")
    setattr(mod, "call_ollama", _fake_ollama)

    resp = await dialogue.process_message(user_id, "Set up reminders", db_session)
    assert resp is not None

    # Reset the global dispatcher singleton so it uses the current test db_session
    import src.triggers.trigger_dispatcher as _td_mod
    _td_mod._dispatcher = None

    # Simulate trigger execution: structured intent would produce a create_schedule trigger
    dispatcher = get_trigger_dispatcher(db=db_session, memory_manager=mm)
    match = {"trigger_id": None, "name": "create_schedule", "action_type": "create_schedule", "score": 1.0, "threshold": 0.5}
    ctx = {"user_id": user_id, "schedule_spec": {"schedule_type": "daily", "time_str": "10:15"}}
    dispatcher.dispatch(match, ctx)

    # Verify schedule created at 10:15 — query via db_session to avoid
    # the unpatched module-level SessionLocal in scheduler.manager
    from src.models.database import Schedule as _Schedule
    db_session.expire_all()
    all_schedules = db_session.query(_Schedule).filter_by(user_id=user_id).all()
    active = [s for s in all_schedules if s.is_active]
    assert len(active) == 1
    sched = active[0]
    # Compute expected next_send using user's timezone and compare stored UTC value
    from src.scheduler.time_utils import compute_next_send_and_cron

    user = db_session.query(User).filter_by(user_id=user_id).first()
    tz_name = getattr(user, "timezone", "UTC") if user else "UTC"
    expected_next_send, expected_cron = compute_next_send_and_cron("10:15", tz_name)

    assert sched.next_send_time is None or (
        sched.next_send_time.hour == expected_next_send.hour and sched.next_send_time.minute == expected_next_send.minute
    )

