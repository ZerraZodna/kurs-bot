"""Unit tests for lesson repeat and memory conflict resolution."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from datetime import datetime, timezone, timedelta

from src.memories.constants import MemoryKey, MemoryCategory


class TestLessonRepeatOffered:
    """Tests for lesson repeat offered functionality."""

    def test_lesson_repeat_offered_constant_exists(self):
        """Test that LESSON_REPEAT_OFFERED constant exists."""
        assert hasattr(MemoryKey, 'LESSON_REPEAT_OFFERED')
        assert MemoryKey.LESSON_REPEAT_OFFERED == "lesson_repeat_offered"

    def test_advance_stores_lesson_repeat_offered(self):
        """Test that advance.py stores lesson_repeat_offered when offering repeat."""
        from src.lessons import advance
        
        # Create mock objects
        mock_memory_manager = MagicMock()
        mock_session = MagicMock()
        mock_prompt_builder = MagicMock()
        mock_call_ollama = MagicMock()
        
        # Configure memory_manager/db user state so compute_current_lesson_state advances by day
        mock_user = MagicMock()
        mock_user.lesson = 28
        mock_user.last_active_at = datetime.now(timezone.utc) - timedelta(days=1)
        mock_memory_manager.db.query.return_value.filter.return_value.first.return_value = mock_user

        # Mock the lesson
        mock_lesson = MagicMock()
        mock_lesson.lesson_id = 29
        mock_lesson.title = "Lesson 29"
        mock_lesson.content = "Content of lesson 29"
        mock_session.query.return_value.filter.return_value.first.return_value = mock_lesson
        
        # Mock format_lesson_message to return simple message
        async def mock_format(lesson, lang, call_ollama):
            return "Lesson content"
        
        # Run the function
        import asyncio
        result = asyncio.run(
            advance.maybe_send_next_lesson(
                user_id=123,
                text="hi",
                session=mock_session,
                prompt_builder=mock_prompt_builder,
                memory_manager=mock_memory_manager,
                call_ollama=mock_call_ollama,
            )
        )
        
        # Verify store_memory was called (multiple times - for current_lesson and lesson_repeat_offered)
        assert mock_memory_manager.store_memory.call_count >= 1
        
        # Check that at least one call was made with lesson_repeat_offered
        call_args_list = mock_memory_manager.store_memory.call_args_list
        keys_stored = [call[1].get("key") for call in call_args_list]
        assert MemoryKey.LESSON_REPEAT_OFFERED in keys_stored, f"Expected lesson_repeat_offered in keys: {keys_stored}"


class TestConfirmYesLessonRepeat:
    """Tests for confirm_yes handler with lesson_repeat context."""

    @pytest.mark.asyncio
    async def test_confirm_yes_with_lesson_repeat_context(self):
        """Test that confirm_yes returns lesson content when context is lesson_repeat."""
        from src.functions.executor import FunctionExecutor
        
        # Create mock objects
        executor = FunctionExecutor()
        
        mock_memory_manager = MagicMock()
        mock_memory_manager.get_memory.return_value = [
            {"memory_id": 1, "value": "28"}
        ]
        
        mock_session = MagicMock()
        mock_lesson = MagicMock()
        mock_lesson.lesson_id = 28
        mock_lesson.title = "Lesson 28"
        mock_lesson.content = "Content of lesson 28"
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_lesson
        
        context = {
            "user_id": 123,
            "memory_manager": mock_memory_manager,
            "session": mock_session
        }
        
        params = {"context": "lesson_repeat"}
        
        # Call the handler
        result = await executor._handle_confirm_yes(params, context)
        
        # Verify the result
        assert result["ok"] is True
        assert result["confirmed"] is True
        assert result["context"] == "lesson_repeat"
        assert result["lesson_id"] == 28
        assert result["title"] == "Lesson 28"
        
        # Verify archive was called to clear the offered memory
        mock_memory_manager.archive_memories.assert_called_once_with(123, [1])

    @pytest.mark.asyncio
    async def test_confirm_yes_without_lesson_repeat_context(self):
        """Test that confirm_yes works normally for other contexts."""
        from src.functions.executor import FunctionExecutor
        
        executor = FunctionExecutor()
        
        mock_memory_manager = MagicMock()
        
        context = {
            "user_id": 123,
            "memory_manager": mock_memory_manager,
            "session": None
        }
        
        params = {"context": "general"}
        
        result = await executor._handle_confirm_yes(params, context)
        
        assert result["ok"] is True
        assert result["confirmed"] is True
        assert result["context"] == "general"
        
        # Should store confirmation
        mock_memory_manager.store_memory.assert_called_once()
