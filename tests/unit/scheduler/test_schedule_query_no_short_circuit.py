"""Test that schedule queries don't short-circuit function calling.

This test verifies that the fix for the issue where "remind me next two hours..."
was incorrectly treated as a status query instead of flowing through to the
function calling system.
"""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.orm import Session

from src.scheduler.schedule_handlers import handle_schedule_messages


@pytest.mark.asyncio
async def test_remind_me_next_two_hours_does_not_short_circuit():
    """Verify 'remind me next two hours...' flows through to function calling.

    This was the original bug: the message 'remind me next two hours to read the daily lesson'
    was being incorrectly matched by detect_schedule_status_request and returning
    a list of existing reminders instead of letting the LLM create a new reminder.
    """
    # Setup mocks
    mock_session = MagicMock(spec=Session)
    mock_memory_manager = MagicMock()
    # No pending schedule request
    mock_memory_manager.get_memory.return_value = []
    mock_onboarding_service = MagicMock()
    mock_schedule_request_handler = AsyncMock(return_value=None)
    mock_call_ollama = AsyncMock()

    # The problematic message that was being short-circuited
    text = "remind me next two hours to read the daily lesson"

    # Call the function
    result = await handle_schedule_messages(
        user_id=1,
        text=text,
        session=mock_session,
        memory_manager=mock_memory_manager,
        onboarding_service=mock_onboarding_service,
        schedule_request_handler=mock_schedule_request_handler,
        call_ollama=mock_call_ollama,
    )

    # The function should return None, allowing the message to flow through
    # to the LLM and function calling system
    assert result is None, (
        f"Expected None to allow function calling, but got: {result}. "
        f"The message '{text}' should not be short-circuited."
    )

    # Verify schedule_request_handler was not called (no short-circuit)
    mock_schedule_request_handler.assert_not_called()


@pytest.mark.asyncio
async def test_remind_me_in_duration_does_not_short_circuit():
    """Verify various 'remind me in...' patterns don't short-circuit."""
    mock_session = MagicMock(spec=Session)
    mock_memory_manager = MagicMock()
    # No pending schedule request
    mock_memory_manager.get_memory.return_value = []
    mock_onboarding_service = MagicMock()
    mock_schedule_request_handler = AsyncMock(return_value=None)
    mock_call_ollama = AsyncMock()

    test_messages = [
        "remind me in 2 hours to read the lesson",
        "remind me in 30 minutes about the daily lesson",
        "remind me tomorrow at 9am to do my lesson",
        "remind me next week about the course",
        "can you remind me in 5 minutes to take a break",
    ]

    for text in test_messages:
        result = await handle_schedule_messages(
            user_id=1,
            text=text,
            session=mock_session,
            memory_manager=mock_memory_manager,
            onboarding_service=mock_onboarding_service,
            schedule_request_handler=mock_schedule_request_handler,
            call_ollama=mock_call_ollama,
        )

        assert result is None, f"Message '{text}' should not be short-circuited, but got: {result}"


@pytest.mark.asyncio
async def test_explicit_daily_schedule_with_time_still_works():
    """Verify explicit daily schedule setting still works (pre-LLM)."""
    mock_session = MagicMock(spec=Session)
    mock_memory_manager = MagicMock()
    # No pending schedule request
    mock_memory_manager.get_memory.return_value = []
    mock_onboarding_service = MagicMock()
    mock_schedule_request_handler = AsyncMock(return_value=None)
    mock_call_ollama = AsyncMock()

    # This should still be handled pre-LLM as it's an explicit daily schedule request
    text = "set my daily reminder for 09:00"

    with patch("src.scheduler.schedule_handlers.scheduler_api") as mock_scheduler:
        mock_scheduler.get_user_schedules.return_value = []
        mock_scheduler.parse_time_string.return_value = (9, 0)

        result = await handle_schedule_messages(
            user_id=1,
            text=text,
            session=mock_session,
            memory_manager=mock_memory_manager,
            onboarding_service=mock_onboarding_service,
            schedule_request_handler=mock_schedule_request_handler,
            call_ollama=mock_call_ollama,
        )

        # This should return a response (not None) because it's an explicit daily schedule
        assert result is not None
        assert "09:00" in result or "daily" in result.lower()


@pytest.mark.asyncio
async def test_pause_request_still_works():
    """Verify pause requests are still handled pre-LLM."""
    mock_session = MagicMock(spec=Session)
    mock_memory_manager = MagicMock()
    # No pending schedule request
    mock_memory_manager.get_memory.return_value = []
    mock_onboarding_service = MagicMock()
    mock_schedule_request_handler = AsyncMock(return_value=None)
    mock_call_ollama = AsyncMock()

    text = "pause my reminders"

    with patch("src.scheduler.schedule_handlers.scheduler_api") as mock_scheduler:
        mock_scheduler.deactivate_user_schedules.return_value = 1

        result = await handle_schedule_messages(
            user_id=1,
            text=text,
            session=mock_session,
            memory_manager=mock_memory_manager,
            onboarding_service=mock_onboarding_service,
            schedule_request_handler=mock_schedule_request_handler,
            call_ollama=mock_call_ollama,
        )

        assert result is not None
        assert "paused" in result.lower()
