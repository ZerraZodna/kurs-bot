"""
Migrated tests for next day confirmation flow.
 migrated from tests/test_next_day_confirmation.py
"""
import pytest
import asyncio
from pathlib import Path
import sys
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.models.database import Lesson, SessionLocal
from tests.fixtures.users import create_test_user
from src.memories import MemoryManager
from src.lessons.state import (
    get_last_sent_lesson_id,
    set_current_lesson,
    set_last_sent_lesson_id,
)
from src.services.dialogue.command_handlers import handle_debug_next_day
from src.lessons.advance import maybe_send_next_lesson
from src.services.dialogue.reminder_handler import handle_lesson_confirmation
from src.language.prompt_builder import PromptBuilder
from src.memories.scheduler_helpers import (
    get_pending_confirmation,
    is_auto_advance_lessons_enabled,
    set_auto_advance_lessons_preference,
)


@pytest.mark.asyncio
@pytest.mark.serial
async def test_next_day_triggers_confirmation_prompt():
    """Given: A user who has completed onboarding with lesson 8
    When: The next day is triggered and maybe_send_next_lesson is called
    Then: A confirmation prompt is sent and pending confirmation is stored
    """
    db = SessionLocal()
    user_id = create_test_user(db, "test_next_day_user")

    mm = MemoryManager(db)
    # Simulate onboarding where the user reported they're on lesson 8
    set_current_lesson(mm, user_id, 8)

    # Call debug next_day to advance debug offset (simulates passage of a day)
    resp = handle_debug_next_day("next_day", mm, db, user_id)
    # debug handler should at least return 'OK' when no schedules exist
    assert resp in ("OK", None) or isinstance(resp, str)

    # Now call maybe_send_next_lesson directly to see what would be auto-sent
    prompt_builder = PromptBuilder(db, mm)
    result = await maybe_send_next_lesson(
        user_id=user_id,
        text="Hi",
        session=db,
        prompt_builder=prompt_builder,
        memory_manager=mm,
        call_ollama=lambda p, m=None, language=None: asyncio.sleep(0) or "",
    )

    assert result is not None, "Expected a confirmation prompt but got None"
    assert "gentle, loving" in result.lower() or "mildt, kjærlig" in result.lower()

    # Verify that a pending confirmation was persisted for the user
    pending = get_pending_confirmation(mm, user_id)
    assert pending is not None, "Expected a pending confirmation to be stored"
    assert int(pending.get("lesson_id")) == 8

    # If we greet again in the same session/day we should NOT re-send the
    # confirmation prompt; the pending entry protects against repeated
    # messages which confused users.
    result2 = await maybe_send_next_lesson(
        user_id=user_id,
        text="Hi again",
        session=db,
        prompt_builder=prompt_builder,
        memory_manager=mm,
        call_ollama=lambda p, m=None, language=None: asyncio.sleep(0) or "",
    )
    assert result2 is None, "Second greeting should not trigger another prompt"

    # Also verify that the original prompt no longer contains the word
    # 'yesterday' since we updated the wording to avoid day-boundary
    # assumptions.
    assert "yesterday" not in result.lower()

    db.close()


def test_confirmation_prompt_wording():
    """Given: A lesson confirmation prompt template
    When: The template is retrieved
    Then: It uses the updated wording without 'yesterday'
    """
    # direct check of the template helper to ensure updated language
    from src.language.onboarding_prompts import get_lesson_confirmation_prompt

    prompt_en = get_lesson_confirmation_prompt("en", 9)
    assert "yesterday" not in prompt_en.lower()
    assert "lesson 9" in prompt_en.lower()
    assert "move forward" in prompt_en.lower()
    assert "stay with this lesson" in prompt_en.lower()

    prompt_no = get_lesson_confirmation_prompt("no", 12)
    # norwegian text should also avoid the literal word for "yesterday"
    assert "i går" not in prompt_no.lower()
    assert "leksjon 12" in prompt_no.lower()
    assert "gå videre" in prompt_no.lower()
    assert "bli på denne leksjonen" in prompt_no.lower()


@pytest.mark.asyncio
@pytest.mark.serial
async def test_next_day_auto_advance_preference_skips_confirmation_prompt():
    """Given: A user with auto-advance preference enabled
    When: The next day is triggered
    Then: Next lesson is sent without confirmation prompt
    """
    db = SessionLocal()
    user_id = create_test_user(db, "test_next_day_auto_assume")

    mm = MemoryManager(db)
    set_current_lesson(mm, user_id, 8)
    set_auto_advance_lessons_preference(mm, user_id, True, source="test")

    if db.query(Lesson).filter(Lesson.lesson_id == 9).first() is None:
        db.add(
            Lesson(
                lesson_id=9,
                title="Lesson Nine",
                content="Lesson nine content.",
                created_at=datetime.now(timezone.utc),
            )
        )
        db.commit()

    async def _fake_call_ollama(prompt, model=None, language=None):
        return ""

    prompt_builder = PromptBuilder(db, mm)
    result = await maybe_send_next_lesson(
        user_id=user_id,
        text="Hi",
        session=db,
        prompt_builder=prompt_builder,
        memory_manager=mm,
        call_ollama=_fake_call_ollama,
    )

    assert result is not None
    assert "Lesson 9" in result
    assert get_pending_confirmation(mm, user_id) is None
    assert get_last_sent_lesson_id(mm, user_id) == 9

    db.close()


@pytest.mark.asyncio
@pytest.mark.serial
async def test_auto_advance_intent_is_persisted_and_negative_override_adjusts_progress():
    """Given: A user who has auto-advance enabled
    When: User says they did not do the lesson
    Then: Auto-advance is disabled and progress is adjusted
    """
    db = SessionLocal()
    user_id = create_test_user(db, "test_next_day_auto_assume_override")
    mm = MemoryManager(db)
    set_last_sent_lesson_id(mm, user_id, 9)

    async def _fake_translate(text: str, language: str):
        return text

    async def _fake_format_lesson(lesson, language: str):
        return f"Lesson {lesson.lesson_id}: {lesson.title}"

    response = await handle_lesson_confirmation(
        user_id=user_id,
        text="Assume I do one lesson each day.",
        session=db,
        memory_manager=mm,
        onboarding_service=None,
        translate_fn=_fake_translate,
        get_language_fn=lambda uid: "en",
        format_lesson_fn=_fake_format_lesson,
    )
    assert response is not None
    assert "auto-advance" in response.lower()
    assert is_auto_advance_lessons_enabled(mm, user_id) is True

    override_response = await handle_lesson_confirmation(
        user_id=user_id,
        text="I did not do it.",
        session=db,
        memory_manager=mm,
        onboarding_service=None,
        translate_fn=_fake_translate,
        get_language_fn=lambda uid: "en",
        format_lesson_fn=_fake_format_lesson,
    )
    assert override_response is not None
    assert "keep you on lesson 8" in override_response.lower()
    assert get_last_sent_lesson_id(mm, user_id) == 8

    db.close()


@pytest.mark.asyncio
@pytest.mark.serial
async def test_scheduler_full_two_day_flow_after_onboarding():
    """Given: A user who completed onboarding reporting lesson 17
       (current_lesson=17, last_sent_lesson_id=None)
    When: Day 1 scheduler fires, user confirms 'yes', then Day 2 scheduler fires
    Then:
      - Day 1: confirmation prompt for lesson 17 is sent
      - After 'yes': lesson 18 is delivered, last_sent=18
      - Day 2: confirmation prompt for lesson 18 is sent
      - After 'yes': lesson 19 is delivered, last_sent=19
    """
    from src.scheduler.execution import execute_scheduled_task
    from src.scheduler.core import SchedulerService

    db = SessionLocal()
    user_id = create_test_user(db, "test_two_day_flow_user")

    mm = MemoryManager(db)
    # Day 0: Onboarding sets current_lesson=17, last_sent=None
    set_current_lesson(mm, user_id, 17)

    # Verify initial state
    assert get_last_sent_lesson_id(mm, user_id) is None, "last_sent should be None after onboarding"

    # Seed lessons 17, 18, 19 if not present
    for lid in (17, 18, 19):
        if db.query(Lesson).filter(Lesson.lesson_id == lid).first() is None:
            db.add(
                Lesson(
                    lesson_id=lid,
                    title=f"Lesson {lid} Title",
                    content=f"Lesson {lid} content text.",
                    created_at=datetime.now(timezone.utc),
                )
            )
    db.commit()

    # Create a daily schedule for the user
    schedule = SchedulerService.create_daily_schedule(
        user_id=user_id, lesson_id=None, time_str="09:00", session=db
    )

    # ---- DAY 1: Scheduler fires ----
    result_day1 = execute_scheduled_task(schedule.schedule_id, simulate=True, session=db)
    assert result_day1 is not None, "Day 1: scheduler should return messages"
    combined_day1 = "\n\n".join(result_day1) if isinstance(result_day1, list) else str(result_day1)

    # Should be a confirmation prompt for lesson 17
    assert "gentle, loving" in combined_day1.lower() or "mildt, kjærlig" in combined_day1.lower(), \
        f"Day 1: Expected confirmation prompt, got: {combined_day1}"
    assert "17" in combined_day1, f"Day 1: Expected lesson 17 mentioned, got: {combined_day1}"

    # Verify pending confirmation is set
    pending_day1 = get_pending_confirmation(mm, user_id)
    assert pending_day1 is not None, "Day 1: Expected pending confirmation"
    assert int(pending_day1.get("lesson_id")) == 17, f"Day 1: Expected pending for lesson 17, got {pending_day1}"

    # ---- User confirms 'yes' on Day 1 ----
    async def _fake_translate(text: str, language: str):
        return text

    async def _fake_format_lesson(lesson, language: str):
        return f"Lesson {lesson.lesson_id}: {lesson.title}\n\n{lesson.content}"

    # Mock _semantic_yes_no to isolate this test from trigger matcher
    # singleton caching. A dedicated test in test_ci_trigger_data_completeness
    # verifies that the real _semantic_yes_no works with CI trigger data.
    import src.services.dialogue.reminder_handler as _rh
    _orig_semantic = _rh._semantic_yes_no

    async def _mock_semantic_yes_no(text, onboarding_service):
        if text.strip().lower() in ("yes", "ja", "y"):
            return (True, False)
        if text.strip().lower() in ("no", "nei", "n"):
            return (False, True)
        return await _orig_semantic(text, onboarding_service)

    _rh._semantic_yes_no = _mock_semantic_yes_no
    try:
        confirmation_response = await handle_lesson_confirmation(
            user_id=user_id,
            text="yes",
            session=db,
            memory_manager=mm,
            onboarding_service=None,
            translate_fn=_fake_translate,
            get_language_fn=lambda uid: "en",
            format_lesson_fn=_fake_format_lesson,
        )
    finally:
        _rh._semantic_yes_no = _orig_semantic

    assert confirmation_response is not None, "Day 1 confirmation: Expected lesson delivery response"
    assert "18" in confirmation_response, f"Day 1 confirmation: Expected lesson 18, got: {confirmation_response}"

    # Verify last_sent is now 18
    last_sent_after_confirm = get_last_sent_lesson_id(mm, user_id)
    assert last_sent_after_confirm == 18, f"After Day 1 confirm: Expected last_sent=18, got {last_sent_after_confirm}"

    # Verify pending confirmation is resolved
    pending_after_confirm = get_pending_confirmation(mm, user_id)
    assert pending_after_confirm is None, "After Day 1 confirm: pending should be resolved"

    # ---- DAY 2: Scheduler fires again ----
    result_day2 = execute_scheduled_task(schedule.schedule_id, simulate=True, session=db)
    assert result_day2 is not None, "Day 2: scheduler should return messages"
    combined_day2 = "\n\n".join(result_day2) if isinstance(result_day2, list) else str(result_day2)

    # Should be a confirmation prompt for lesson 18
    assert "gentle, loving" in combined_day2.lower() or "mildt, kjærlig" in combined_day2.lower(), \
        f"Day 2: Expected confirmation prompt, got: {combined_day2}"
    assert "18" in combined_day2, f"Day 2: Expected lesson 18 mentioned, got: {combined_day2}"

    # Verify pending confirmation is set for lesson 18
    pending_day2 = get_pending_confirmation(mm, user_id)
    assert pending_day2 is not None, "Day 2: Expected pending confirmation"
    assert int(pending_day2.get("lesson_id")) == 18, f"Day 2: Expected pending for lesson 18, got {pending_day2}"

    # ---- User confirms 'yes' on Day 2 ----
    _rh._semantic_yes_no = _mock_semantic_yes_no
    try:
        confirmation_response_day2 = await handle_lesson_confirmation(
            user_id=user_id,
            text="yes",
            session=db,
            memory_manager=mm,
            onboarding_service=None,
            translate_fn=_fake_translate,
            get_language_fn=lambda uid: "en",
            format_lesson_fn=_fake_format_lesson,
        )
    finally:
        _rh._semantic_yes_no = _orig_semantic

    assert confirmation_response_day2 is not None, "Day 2 confirmation: Expected lesson delivery response"
    assert "19" in confirmation_response_day2, f"Day 2 confirmation: Expected lesson 19, got: {confirmation_response_day2}"

    # Verify last_sent is now 19
    last_sent_after_day2 = get_last_sent_lesson_id(mm, user_id)
    assert last_sent_after_day2 == 19, f"After Day 2 confirm: Expected last_sent=19, got {last_sent_after_day2}"

    db.close()


@pytest.mark.asyncio
@pytest.mark.serial
async def test_auto_advance_preference_can_be_disabled_by_user_intent():
    """Given: A user with auto-advance enabled
    When: User explicitly disables it
    Then: Auto-advance preference is disabled
    """
    db = SessionLocal()
    user_id = create_test_user(db, "test_next_day_auto_assume_disable")
    mm = MemoryManager(db)
    set_auto_advance_lessons_preference(mm, user_id, True, source="test")

    async def _fake_translate(text: str, language: str):
        return text

    async def _fake_format_lesson(lesson, language: str):
        return f"Lesson {lesson.lesson_id}: {lesson.title}"

    response = await handle_lesson_confirmation(
        user_id=user_id,
        text="Don't assume I do one lesson each day.",
        session=db,
        memory_manager=mm,
        onboarding_service=None,
        translate_fn=_fake_translate,
        get_language_fn=lambda uid: "en",
        format_lesson_fn=_fake_format_lesson,
    )

    assert response is not None
    assert "ask for confirmation" in response.lower()
    assert is_auto_advance_lessons_enabled(mm, user_id) is False

    db.close()
