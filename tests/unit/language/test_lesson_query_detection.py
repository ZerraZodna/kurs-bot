"""Unit tests for lesson query detection.

Migrated from tests/test_lesson_query_detection.py to use new test fixtures.
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.lessons.handler import detect_lesson_request, process_lesson_query
from src.models.database import Base, Lesson


@pytest.fixture()
def lessons_db_session():
    """Create a test database with lesson data."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add_all(
        [
            Lesson(lesson_id=1, title="Lesson 1", content="Full lesson 1 text"),
            Lesson(lesson_id=7, title="Lesson 7", content="Full lesson 7 text"),
            Lesson(lesson_id=13, title="Lesson 13", content="Full lesson 13 text"),
            Lesson(lesson_id=14, title="Lesson 14", content="Full lesson 14 text"),
        ]
    )
    session.commit()
    yield session
    session.close()


class TestDetectLessonRequest:
    """Tests for lesson request detection."""

    @pytest.mark.parametrize(
        "text,expected",
        [
            ("Give me lesson 13", {"lesson_id": 13}),
            ("What is lesson 14", {"lesson_id": 14}),
            ("Give me lesson text 13", {"lesson_id": 13}),
            ("Gi meg lekse 13", {"lesson_id": 13}),
            ("What is today's lesson?", None),  # Now handled by AI function calling
            ("Hva er dagens lekse i dag?", None),  # Now handled by AI function calling
        ],
    )
    def test_detect_lesson_request_variants(self, text, expected):
        """Given: Various text inputs requesting lessons
        When: Calling detect_lesson_request
        Then: Should correctly detect lesson ID or return None for today requests
        (today's lesson now handled by AI function calling system)
        """
        assert detect_lesson_request(text) == expected


class _PromptBuilderStub:
    """Stub for prompt builder."""
    def __init__(self, lesson_id: int):
        self.lesson_id = lesson_id

    def get_today_lesson_context(self, user_id: int):
        return {"state": {"lesson_id": self.lesson_id}}


class TestProcessLessonQuery:
    """Tests for processing lesson queries."""

    @pytest.mark.asyncio
    async def test_process_lesson_query_prefers_explicit_number_over_semantic_short_circuit(
        self, monkeypatch, lessons_db_session
    ):
        """Given: User requests specific lesson by number
        When: Processing the query
        Then: Should use explicit lesson ID, not semantic short-circuit
        """
        async def _should_not_be_called(*args, **kwargs):
            raise AssertionError("semantic short-circuit should not run for explicit lesson ids")

        monkeypatch.setattr(
            "src.lessons.handler.pre_llm_lesson_short_circuit", _should_not_be_called
        )

        response = await process_lesson_query(
            user_id=1,
            text="Give me lesson text 13",
            session=lessons_db_session,
            prompt_builder=_PromptBuilderStub(lesson_id=1),
            memory_manager=None,
            onboarding_flow=None,
            onboarding_service=None,
            user_language="en",
        )

        assert response is not None
        assert "Lesson 13" in response
        assert "Full lesson 13 text" in response

    @pytest.mark.asyncio
    async def test_process_lesson_query_today_returns_none_for_function_calling(
        self, monkeypatch, lessons_db_session
    ):
        """Given: User requests today's lesson
        When: Processing the query
        Then: Should return None to let AI function calling handle it
        (today's lesson now handled by send_todays_lesson function)
        """
        response = await process_lesson_query(
            user_id=1,
            text="Hva er dagens lekse i dag?",
            session=lessons_db_session,
            prompt_builder=_PromptBuilderStub(lesson_id=7),
            memory_manager=None,
            onboarding_flow=None,
            onboarding_service=None,
            user_language="en",
        )

        # Should return None so AI function calling can handle "today's lesson"
        assert response is None
