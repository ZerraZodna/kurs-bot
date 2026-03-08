"""Unit tests for unit schedule (user's current lesson in schedule context).

Tests the flow where:
1. User reports their current lesson (e.g., "I am on lesson 26")
2. Memory is stored with current lesson
3. User asks for today's lesson
4. System returns the lesson from memory (lesson 26)
"""

import pytest

from src.models.database import Lesson
from src.services.dialogue_engine import DialogueEngine
from src.memories import MemoryManager
from src.lessons.state import get_current_lesson, set_current_lesson
from tests.fixtures.users import make_ready_user


def _ensure_lesson(session, lesson_id: int, title: str, content: str):
    """Ensure a lesson exists in the database."""
    existing = session.query(Lesson).filter_by(lesson_id=lesson_id).first()
    if not existing:
        lesson = Lesson(lesson_id=lesson_id, title=title, content=content)
        session.add(lesson)
        session.commit()
    return session.query(Lesson).filter_by(lesson_id=lesson_id).first()


class TestUnitScheduleCurrentLesson:
    """Tests for unit schedule with current lesson tracking."""

    @pytest.mark.asyncio
    async def test_user_reports_lesson_then_asks_for_todays_lesson(
        self, db_session, monkeypatch, mock_ollama_client
    ):
        """Given: A new user
        When: User says "I am on lesson 26"
        And: User asks for "today's lesson"
        Then: The system should return lesson 26 from memory
        """
        # Setup: Create ready user and ensure lesson 26 exists
        user_id = make_ready_user(db_session, external_id="test_unit_schedule_001", first_name="Test")
        
        # Ensure lesson 26 exists in DB
        _ensure_lesson(
            db_session, 
            lesson_id=26, 
            title="Lesson 26", 
            content="Myriad forms the holy Son of God appears.\n\nLesson 26 content goes here."
        )
        
        # Also ensure lesson 1 exists (for fallback)
        _ensure_lesson(db_session, 1, "Lesson 1", "Nothing I see means anything.\n\nLesson 1 content.")
        
        # Create DialogueEngine
        engine = DialogueEngine(db_session)

        # Skip onboarding for this test
        monkeypatch.setattr(engine.onboarding, "should_show_onboarding", lambda uid: False)
        
        # First: User says "I am on lesson 26"
        response1 = await engine.process_message(user_id, "I am on lesson 26", db_session)
        
        # Verify memory was stored
        mm = MemoryManager(db_session)
        current_lesson = get_current_lesson(mm, user_id)
        assert current_lesson == 26, f"Expected current_lesson=26, got {current_lesson}"
        
        # Second: User asks for "today's lesson"
        response2 = await engine.process_message(user_id, "Give me today's lesson", db_session)
        
        # Verify the response contains lesson 26 content
        assert response2 is not None
        
        # Check that we got lesson 26 in the response
        response_text = str(response2)
        
        # Verify the lesson content is from lesson 26
        assert "26" in response_text or "Lesson 26" in response_text, \
            f"Expected lesson 26 in response, got: {response_text[:200]}"

    @pytest.mark.asyncio
    async def test_todays_lesson_returns_lesson_from_memory(
        self, db_session, monkeypatch, mock_ollama_client
    ):
        """Given: A user with lesson 26 stored in memory
        When: User asks for today's lesson
        Then: The function executor returns lesson 26 content
        """
        # Setup: Create ready user and ensure lesson 26 exists
        user_id = make_ready_user(db_session, external_id="test_unit_schedule_002", first_name="Test")
        
        # Ensure lesson 26 exists in DB
        lesson_26 = _ensure_lesson(
            db_session, 
            lesson_id=26, 
            title="Lesson 26", 
            content="Myriad forms the holy Son of God appears.\n\nLesson 26 content goes here."
        )
        
        # Set up memory with current lesson = 26
        mm = MemoryManager(db_session)
        set_current_lesson(mm, user_id, 26)
        
        # Verify memory is set
        current_lesson = get_current_lesson(mm, user_id)
        assert current_lesson == 26
        
        # Create DialogueEngine
        engine = DialogueEngine(db_session)
        
        # Skip onboarding for this test
        monkeypatch.setattr(engine.onboarding, "should_show_onboarding", lambda uid: False)
        
        # User asks for today's lesson
        response = await engine.process_message(user_id, "Give me today's lesson", db_session)
        
        # Verify response contains lesson 26
        assert response is not None
        response_str = str(response)
        assert "26" in response_str or "Lesson 26" in response_str, \
            f"Expected lesson 26 in response, got: {response_str[:200]}"


class TestUnitScheduleFunctionExecutor:
    """Tests for FunctionExecutor handling of send_todays_lesson with lesson memory."""

    @pytest.fixture
    def executor(self):
        """Create a FunctionExecutor instance."""
        from src.functions.executor import FunctionExecutor
        return FunctionExecutor()

    @pytest.mark.asyncio
    async def test_send_todays_lesson_uses_memory_lesson(
        self, executor, db_session, test_user
    ):
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
            content="Myriad forms the holy Son of God appears.\n\nLesson 26 content."
        )
        
        # Create context
        context = {
            "user_id": test_user.user_id,
            "session": db_session,
            "memory_manager": mm,
        }
        
        # Execute send_todays_lesson function
        result = await executor._handle_send_todays_lesson({}, context)
        
        # Verify result
        assert result["ok"] is True
        assert result["lesson_id"] == 26
        assert "title" in result
        assert "content" in result

    @pytest.mark.asyncio
    async def test_send_todays_lesson_defaults_to_lesson_1_when_no_memory(
        self, executor, db_session, test_user
    ):
        """Given: User has no lesson in memory
        When: send_todays_lesson function is called
        Then: Returns lesson 1 (default)
        """
        # No memory set - fresh user
        mm = MemoryManager(db_session)
        
        # Ensure lesson 1 exists
        _ensure_lesson(
            db_session, 
            lesson_id=1, 
            title="Lesson 1", 
            content="Nothing I see means anything."
        )
        
        context = {
            "user_id": test_user.user_id,
            "session": db_session,
            "memory_manager": mm,
        }
        
        # Execute send_todays_lesson function
        result = await executor._handle_send_todays_lesson({}, context)
        
        # Verify result defaults to lesson 1
        assert result["ok"] is True
        assert result["lesson_id"] == 1


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

