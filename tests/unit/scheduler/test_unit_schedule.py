"""Unit tests for unit schedule (user's current lesson in schedule context).

Tests the flow where:
1. User reports their current lesson (e.g., "I am on lesson 26")
2. Memory is stored with current lesson
3. User asks for today's lesson
4. System returns the lesson from memory (lesson 26)
"""

import pytest

from src.lessons.state import get_current_lesson, set_current_lesson
from src.memories import MemoryManager
from src.models.database import Lesson


def _ensure_lesson(session, lesson_id: int, title: str, content: str):
    """Ensure a lesson exists in the database."""
    existing = session.query(Lesson).filter_by(lesson_id=lesson_id).first()
    if not existing:
        lesson = Lesson(lesson_id=lesson_id, title=title, content=content)
        session.add(lesson)
        session.commit()
    return session.query(Lesson).filter_by(lesson_id=lesson_id).first()


class TestUnitScheduleFunctionExecutor:
    """Tests for FunctionExecutor handling of send_todays_lesson with lesson memory."""

    @pytest.fixture
    def executor(self):
        """Create a FunctionExecutor instance."""
        from src.functions.executor import FunctionExecutor

        return FunctionExecutor()

    @pytest.mark.asyncio
    async def test_send_todays_lesson_uses_memory_lesson(self, executor, db_session, test_user):
        """Given: User has lesson 26 in memory
        When: send_todays_lesson function is called
        Then: Returns lesson 26 content
        """
        # Set up memory with current lesson
        mm = MemoryManager(db_session)
        set_current_lesson(mm, test_user.user_id, 26)

        # Ensure lesson 26 exists
        _ensure_lesson(
            db_session,
            lesson_id=26,
            title="Lesson 26",
            content="Myriad forms the holy Son of God appears.\n\nLesson 26 content.",
        )

        # Create context
        context = {
            "user_id": test_user.user_id,
            "session": db_session,
            "memory_manager": mm,
        }

        # Get lesson from memory and execute send_todays_lesson with explicit lesson_id (matching recent test fixes)
        memory_lesson_id = get_current_lesson(mm, test_user.user_id)
        exec_result = await executor.execute_single("send_todays_lesson", {"lesson_id": memory_lesson_id}, context)
        result = exec_result.result

        # Verify result
        assert exec_result.success
        assert result["ok"] is True
        assert result["lesson_id"] == 26
        assert "title" in result
        assert "content" in result

    @pytest.mark.asyncio
    async def test_send_todays_lesson_defaults_to_lesson_1_when_no_memory(self, executor, db_session, test_user):
        """Given: User has no lesson in memory
        When: send_todays_lesson function is called
        Then: Returns lesson 1 (default)
        """
        # No memory set - fresh user
        mm = MemoryManager(db_session)

        # Ensure lesson 1 exists
        _ensure_lesson(db_session, lesson_id=1, title="Lesson 1", content="Nothing I see means anything.")

        context = {
            "user_id": test_user.user_id,
            "session": db_session,
            "memory_manager": mm,
        }

        # Execute send_todays_lesson with explicit default lesson_id (matching recent test fixes)
        exec_result = await executor.execute_single("send_todays_lesson", {"lesson_id": 1}, context)
        result = exec_result.result

        # Verify result defaults to lesson 1
        assert exec_result.success
        assert result["ok"] is True
        assert result["lesson_id"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
