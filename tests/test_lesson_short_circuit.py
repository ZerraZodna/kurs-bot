import pytest

from src.models.database import SessionLocal, User, Lesson
from src.services.dialogue_engine import DialogueEngine


@pytest.mark.asyncio
async def test_pre_llm_lesson_short_circuit(monkeypatch):
    # Setup DB objects
    session = SessionLocal()
    user = User(user_id=1, external_id="u1", channel="telegram")
    session.add(user)
    lesson = Lesson(lesson_id=1, title="L1", content="Full lesson text")
    session.add(lesson)
    session.commit()

    engine = DialogueEngine(db=session)

    # Make prompt_builder return today's lesson id
    monkeypatch.setattr(engine.prompt_builder, "get_today_lesson_context", lambda uid: {"state": {"lesson_id": 1}})
    # Skip onboarding for this test so the short-circuit path runs
    monkeypatch.setattr(engine.onboarding, "should_show_onboarding", lambda uid: False)

    # Ensure we do not call the LLM for this short-circuit path
    async def _llm_fail(*args, **kwargs):
        raise AssertionError("LLM should not be called for raw lesson short-circuit")

    monkeypatch.setattr(engine, "call_ollama", _llm_fail)

    resp = await engine.process_message(user_id=1, text="What's today's lesson?", session=session)

    # The short-circuit should return the full lesson formatting (not a brief
    # LLM reply). Assert we receive a lesson header for lesson 1.
    assert "Lesson 1" in resp

    resp = await engine.process_message(user_id=1, text="what is todays lesson", session=session)

    # The short-circuit should return the full lesson formatting (not a brief
    # LLM reply). Assert we receive a lesson header for lesson 1.
    assert "Lesson 1" in resp
