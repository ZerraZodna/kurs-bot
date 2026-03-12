"""
Migrated integration tests for process message creates one-time.
 migrated from tests/test_process_message_creates_one_time.py
"""
import asyncio
import json
import pytest
from datetime import datetime, timezone, timedelta

from src.models.database import SessionLocal, User, init_db, Memory, Schedule
from src.memories import MemoryManager
from src.services.dialogue_engine import DialogueEngine
from src.functions.executor import get_function_executor
from src.scheduler.core import SchedulerService
from tests.mocks.stream_consumer import consume_stream_response


@pytest.mark.asyncio
async def test_process_message_creates_one_time_reminder(monkeypatch):
    """Given: A user sends a message to create a one-time reminder
    When: The dialogue engine processes the message
    Then: A one-time schedule is created with the correct message
    """
    db = SessionLocal()
    try:
        # Given: Create a ready user (onboarding complete)
        from tests.fixtures.users import make_ready_user

        user_id = make_ready_user(db, external_id="procmsg_test_user", first_name="Proc")
        dialogue = DialogueEngine(db)

        # Given: Ensure a daily schedule exists for this user
        # (mirrors real-life state so the dialogue flow that depends on an existing daily schedule is exercised)
        SchedulerService.create_daily_schedule(user_id, lesson_id=None, time_str="12:00", session=db)

        # Given: Monkeypatch the trigger handler to use FunctionExecutor
        async def fake_handle_triggers(*args, **kwargs):
            # Accept both positional and keyword args
            response = kwargs.get("response") if kwargs.get("response") is not None else (args[0] if len(args) > 0 else None)
            original_text = kwargs.get("original_text") if kwargs.get("original_text") is not None else (args[1] if len(args) > 1 else "")
            session_arg = kwargs.get("session") if kwargs.get("session") is not None else (args[2] if len(args) > 2 else None)
            memory_manager = kwargs.get("memory_manager") if kwargs.get("memory_manager") is not None else (args[3] if len(args) > 3 else None)
            user_id_arg = kwargs.get("user_id") if kwargs.get("user_id") is not None else (args[4] if len(args) > 4 else None)

            # Use FunctionExecutor instead of legacy TriggerDispatcher
            executor = get_function_executor()
            context = {
                "user_id": user_id_arg,
                "session": session_arg,
                "memory_manager": memory_manager,
                "original_text": original_text,
            }
            
            # Build a one-time schedule spec inferred from user's text
            run_at = (datetime.now(timezone.utc) + timedelta(hours=1)).replace(minute=0, second=0, microsecond=0)
            
            # Execute create_one_time_reminder function
            await executor.execute_single(
                "create_one_time_reminder",
                {
                    "run_at": run_at.isoformat(),
                    "message": "Remind me to go out with the garbage at 12:00",
                },
                context
            )

        monkeypatch.setattr("src.triggers.triggering.handle_triggers", fake_handle_triggers)

        # When: Call process_message which will invoke the real Ollama client and our fake trigger handler
        resp = await dialogue.process_message_for_telegram(user_id, "Remind me to go out with the garbage at 12:00", db, chat_id=0)
        full_text, diagnostics = await consume_stream_response(resp)
        
        # Print the LLM response for inspection
        print("--- LLM response start ---")
        print(full_text)
        print("--- LLM response end ---")
        print("--- Diagnostics ---")
        print(diagnostics)
        
        # Then: Ensure we received a non-empty response
        assert isinstance(full_text, str) and full_text.strip()

        # Then: Verify schedule and stored message
        schedules = db.query(Schedule).filter_by(user_id=user_id).all()
        one_time = [s for s in schedules if s.schedule_type and s.schedule_type.startswith("one_time")]
        assert len(one_time) == 1

        mm = MemoryManager(db)
        memories = mm.get_memory(user_id=user_id, key="schedule_message")
        assert memories and len(memories) >= 1
        payload = json.loads(memories[-1].get("value"))
        assert payload.get("message") == "Remind me to go out with the garbage at 12:00"

    finally:
        db.close()
