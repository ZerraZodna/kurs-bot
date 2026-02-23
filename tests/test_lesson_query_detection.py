import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.lessons.handler import detect_lesson_request, process_lesson_query
from src.models.database import Base, Lesson


@pytest.fixture()
def db_session():
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


@pytest.mark.parametrize(
    "text,expected",
    [
        ("Give me lesson 13", {"lesson_id": 13}),
        ("What is lesson 14", {"lesson_id": 14}),
        ("Give me lesson text 13", {"lesson_id": 13}),
        ("Gi meg lekse 13", {"lesson_id": 13}),
        ("What is today's lesson?", {"today": True}),
        ("Hva er dagens lekse i dag?", {"today": True}),
    ],
)
def test_detect_lesson_request_variants(text, expected):
    assert detect_lesson_request(text) == expected


class _PromptBuilderStub:
    def __init__(self, lesson_id: int):
        self.lesson_id = lesson_id

    def get_today_lesson_context(self, user_id: int):
        return {"state": {"lesson_id": self.lesson_id}}


@pytest.mark.asyncio
async def test_process_lesson_query_prefers_explicit_number_over_semantic_short_circuit(
    monkeypatch, db_session
):
    async def _should_not_be_called(*args, **kwargs):
        raise AssertionError("semantic short-circuit should not run for explicit lesson ids")

    monkeypatch.setattr(
        "src.lessons.handler.pre_llm_lesson_short_circuit", _should_not_be_called
    )

    response = await process_lesson_query(
        user_id=1,
        text="Give me lesson text 13",
        session=db_session,
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
async def test_process_lesson_query_today_idag_uses_current_lesson_without_semantic(
    monkeypatch, db_session
):
    async def _should_not_be_called(*args, **kwargs):
        raise AssertionError("semantic short-circuit should not run for explicit today lesson requests")

    monkeypatch.setattr(
        "src.lessons.handler.pre_llm_lesson_short_circuit", _should_not_be_called
    )

    response = await process_lesson_query(
        user_id=1,
        text="Hva er dagens lekse i dag?",
        session=db_session,
        prompt_builder=_PromptBuilderStub(lesson_id=7),
        memory_manager=None,
        onboarding_flow=None,
        onboarding_service=None,
        user_language="en",
    )

    assert response is not None
    assert "Lesson 7" in response
    assert "Full lesson 7 text" in response
