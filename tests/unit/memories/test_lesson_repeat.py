"""Unit tests for lesson repeat and memory conflict resolution."""

from unittest.mock import MagicMock

import pytest

from src.memories.constants import MemoryKey


class TestLessonRepeatOffered:
    """Tests for lesson repeat offered functionality."""

    def test_lesson_repeat_offered_constant_exists(self):
        """Test that LESSON_REPEAT_OFFERED constant exists."""
        assert hasattr(MemoryKey, "LESSON_REPEAT_OFFERED")
        assert MemoryKey.LESSON_REPEAT_OFFERED == "lesson_repeat_offered"


class TestConfirmYesLessonRepeat:
    """Tests for confirm_yes handler with lesson_repeat context."""

    @pytest.mark.asyncio
    async def test_confirm_yes_with_lesson_repeat_context(self):
        """Test that confirm_yes returns lesson content when context is lesson_repeat."""
        from src.functions.executor import FunctionExecutor

        # Create mock objects
        executor = FunctionExecutor()

        mock_memory_manager = MagicMock()
        mock_memory_manager.get_memory.return_value = [{"memory_id": 1, "value": "28"}]

        mock_session = MagicMock()
        mock_lesson = MagicMock()
        mock_lesson.lesson_id = 28
        mock_lesson.title = "Lesson 28"
        mock_lesson.content = "Content of lesson 28"
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_lesson

        context = {"user_id": 123, "memory_manager": mock_memory_manager, "session": mock_session}

        params = {"context": "lesson_repeat"}

        # Call the handler
        exec_result = await executor.execute_single("confirm_yes", params, context)
        result = exec_result.result

        # Verify the result
        assert exec_result.success
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

        context = {"user_id": 123, "memory_manager": mock_memory_manager, "session": None}

        params = {"context": "general"}

        exec_result = await executor.execute_single("confirm_yes", params, context)
        result = exec_result.result

        assert exec_result.success
        assert result["ok"] is True
        assert result["confirmed"] is True
        assert result["context"] == "general"

        # Should store confirmation
        mock_memory_manager.store_memory.assert_called_once()
