import logging

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.lessons.handler import handle_lesson_request
from src.models.database import Base, Lesson


@pytest.fixture()
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    session.add(Lesson(lesson_id=1, title="Lesson 1", content="Full lesson text"))
    session.commit()
    yield session
    session.close()


@pytest.mark.asyncio
async def test_semantic_raw_lesson_match_is_used_before_regex(monkeypatch, db_session, caplog):
    class SemanticFirstMatcher:
        async def match_triggers(self, user_text, top_k=3, precomputed_embedding=None):
            return [
                {
                    "action_type": "raw_lesson",
                    "score": 0.92,
                    "threshold": 0.75,
                    "match_source": "vector_index",
                }
            ]

    monkeypatch.setattr(
        "src.triggers.trigger_matcher.get_trigger_matcher",
        lambda: SemanticFirstMatcher(),
    )

    caplog.set_level(logging.INFO)
    response = await handle_lesson_request(
        lesson_id=1,
        user_input="What is the exact text of this lesson?",
        session=db_session,
        user_language="en",
    )
    assert "Lesson 1" in response
    assert '"fallback_path_used": false' in caplog.text


@pytest.mark.asyncio
async def test_regex_fallback_runs_after_semantic_miss(monkeypatch, db_session, caplog):
    class SemanticMissMatcher:
        async def match_triggers(self, user_text, top_k=3, precomputed_embedding=None):
            return [
                {
                    "action_type": "raw_lesson",
                    "score": 0.20,
                    "threshold": 0.75,
                    "match_source": "vector_index",
                }
            ]

    monkeypatch.setattr(
        "src.triggers.trigger_matcher.get_trigger_matcher",
        lambda: SemanticMissMatcher(),
    )

    caplog.set_level(logging.INFO)
    response = await handle_lesson_request(
        lesson_id=1,
        user_input="Please show me the exact words of the lesson.",
        session=db_session,
        user_language="en",
    )
    assert "Lesson 1" in response
    assert '"fallback_path_used": true' in caplog.text
