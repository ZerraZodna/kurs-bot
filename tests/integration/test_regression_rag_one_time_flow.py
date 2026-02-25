"""
Migrated integration tests for RAG mode one-time reminder regression.
 migrated from tests/test_regression_rag_one_time_flow.py
"""
import pytest
from src.config import settings
from datetime import datetime, timezone, timedelta

from src.models.database import SessionLocal, init_db, Schedule
from src.memories import MemoryManager
from src.services.dialogue_engine import DialogueEngine
from src.scheduler.core import SchedulerService


@pytest.mark.asyncio
@pytest.mark.skipif(getattr(settings, "EMBEDDING_BACKEND", "local") == "none",
                    reason="requires embedding backend (local or ollama) to run")
async def test_rag_mode_one_time_reminder_preserves_daily(monkeypatch):
    """Given: A user with RAG mode enabled who creates a one-time reminder
    When: The dialogue engine processes the request
    Then: The daily schedule is preserved and not overwritten
    """
    db = SessionLocal()
    try:
        from tests.fixtures.users import make_ready_user

        # Given: Create a ready user
        user_id = make_ready_user(db, external_id="rag_one_time_user", first_name="RagUser")
        mm = MemoryManager(db)
        mm.store_memory(user_id=user_id, key="user_language", value="en", confidence=0.7, source="test", category="preference")

        # Given: Ensure a daily lesson schedule exists
        SchedulerService.create_daily_schedule(user_id=user_id, lesson_id=None, time_str="09:00", session=db)

        # Given: Enable persistent RAG mode for this user
        mm = MemoryManager(db)
        mm.store_memory(user_id, "rag_mode_enabled", "true", category="conversation", source="test")

        dialogue = DialogueEngine(db)

        # When: Verify listing reminders shows the daily 09:00
        resp1 = await dialogue.process_message(user_id, "list reminders", db)
        assert isinstance(resp1, str)
        assert ("09:00" in resp1) or ("9:00" in resp1)

        # Given: Monkeypatch trigger handler to create a one-time schedule when triggered
        async def fake_handle_triggers(*args, **kwargs):
            response = kwargs.get("response") if kwargs.get("response") is not None else (args[0] if len(args) > 0 else None)
            original_text = kwargs.get("original_text") if kwargs.get("original_text") is not None else (args[1] if len(args) > 1 else "")
            session_arg = kwargs.get("session") if kwargs.get("session") is not None else (args[2] if len(args) > 2 else None)
            memory_manager = kwargs.get("memory_manager") if kwargs.get("memory_manager") is not None else (args[3] if len(args) > 3 else None)
            user_id_arg = kwargs.get("user_id") if kwargs.get("user_id") is not None else (args[4] if len(args) > 4 else None)

            from src.triggers.trigger_dispatcher import get_trigger_dispatcher
            dispatcher = get_trigger_dispatcher(session_arg, memory_manager)
            # Build a one-time schedule spec inferred from user's text
            run_at = (datetime.now(timezone.utc) + timedelta(days=1)).replace(hour=12, minute=0, second=0, microsecond=0)
            spec = {
                "schedule_type": "one_time_reminder",
                "run_at": run_at.isoformat(),
                "message": "Remind me to take out the garbage at 12:00",
            }
            match = {"trigger_id": None, "name": "create_schedule", "action_type": "create_schedule", "score": 1.0, "threshold": 0.0}
            dispatcher.dispatch(match, {"user_id": user_id_arg, "schedule_spec": spec, "original_text": original_text})

        monkeypatch.setattr("src.triggers.triggering.handle_triggers", fake_handle_triggers)

        # Given: Prevent pre-LLM schedule detection
        monkeypatch.setattr(dialogue.onboarding, "detect_schedule_request", lambda text: False)

        # When: Send the one-time reminder while RAG is enabled
        resp2 = await dialogue.process_message(user_id, "Remind me to take out the garbage tomorrow at 12:00", db)
        assert isinstance(resp2, str) and resp2.strip()

        # Then: Verify both schedules exist and daily has not been modified
        schedules = db.query(Schedule).filter_by(user_id=user_id).all()
        daily_schedules = [s for s in schedules if s.schedule_type and s.schedule_type.startswith("daily")]
        one_time_schedules = [s for s in schedules if s.schedule_type and s.schedule_type.startswith("one_time")]

        assert len(daily_schedules) == 1
        assert len(one_time_schedules) == 1

    finally:
        db.close()

