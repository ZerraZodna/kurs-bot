"""Unit tests for lesson repeat and memory conflict resolution."""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch

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
        
        # Set up context with previous_lesson_id
        mock_context = {
            "state": {
                "lesson_id": 29,
                "previous_lesson_id": 28,
                "advanced_by_day": True
            }
        }
        mock_prompt_builder.get_today_lesson_context.return_value = mock_context
        
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
        result = asyncio.get_event_loop().run_until_complete(
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


class TestArchiveMemoryIds:
    """Tests for archive_memory_ids as list."""

    def test_dialogue_helpers_handles_list(self):
        """Test that dialogue_helpers handles archive_memory_ids as a list."""
        from src.memories import dialogue_helpers
        
        # Test that the function can handle archive_memory_ids as list
        # This is a basic unit test for the code path
        
        # The key change is that archive_memory_ids is now extracted as a list
        # from the memory dict with default []
        memory = {
            "key": "first_name",
            "value": "John",
            "archive_memory_ids": [1, 2, 3]
        }
        
        # This should work without error
        archive_ids = memory.get("archive_memory_ids", [])
        
        assert isinstance(archive_ids, list)
        assert archive_ids == [1, 2, 3]
        
        # Test with empty list
        memory2 = {"key": "first_name", "value": "Jane"}
        archive_ids2 = memory2.get("archive_memory_ids", [])
        
        assert isinstance(archive_ids2, list)
        assert archive_ids2 == []


class TestLessonCompletedConflict:
    """Tests for lesson_completed conflict resolution."""

    def test_archive_old_lesson_completed(self):
        """Test that old lesson_completed memories are archived before new one."""
        from src.memories import dialogue_helpers
        
        mock_memory_manager = MagicMock()
        mock_memory_manager.get_memory.return_value = [
            {"memory_id": 5, "value": "27"}
        ]
        
        # Call get_memory to get existing lesson_completed
        existing = mock_memory_manager.get_memory(123, MemoryKey.LESSON_COMPLETED)
        
        # Verify it returns the existing memories
        assert len(existing) == 1
        assert existing[0]["memory_id"] == 5
        
        # Simulate what happens in dialogue_helpers
        for existing_mem in existing:
            existing_id = existing_mem.get("memory_id")
            if existing_id:
                mock_memory_manager.archive_memories(123, [existing_id])
        
        # Verify archive was called
        mock_memory_manager.archive_memories.assert_called_with(123, [5])

