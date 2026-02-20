import pytest

from src.models.database import SessionLocal, User, Lesson
from src.services.dialogue_engine import DialogueEngine
from src.services.dialogue.lesson_handler import process_lesson_query


@pytest.mark.asyncio
async def test_pre_llm_lesson_short_circuit(monkeypatch):
    # Setup DB objects and mark onboarding complete so extractor/LLM isn't called
    session = SessionLocal()
    from tests.utils import make_ready_user

    user_id = make_ready_user(session, external_id="u1", first_name="Test")
    lesson = Lesson(lesson_id=1, title="L1", content="Full lesson text")
    session.add(lesson)
    session.commit()

    engine = DialogueEngine(db=session)

    # Make prompt_builder return today's lesson id
    monkeypatch.setattr(engine.prompt_builder, "get_today_lesson_context", lambda uid: {"state": {"lesson_id": 1}})
    # Skip onboarding for this test so the short-circuit path runs
    monkeypatch.setattr(engine.onboarding, "should_show_onboarding", lambda uid: False)

    # Ensure we do not call the LLM for this short-circuit path. Patch the
    # module-level `call_ollama` that other code paths may call, not just the
    # instance method, to make the test robust when run as part of the full
    # suite.
    async def _llm_fail(*args, **kwargs):
        raise AssertionError("LLM should not be called for raw lesson short-circuit")

    monkeypatch.setattr("src.services.dialogue.call_ollama", _llm_fail)
    # Also patch the lower-level client entrypoint in case other modules import
    # the callable directly (ensures robustness when tests run in different orders).
    monkeypatch.setattr("src.services.dialogue.ollama_client.call_ollama", _llm_fail, raising=False)

    resp = await process_lesson_query(
        user_id=user_id,
        text="What's today's lesson?",
        session=session,
        prompt_builder=engine.prompt_builder,
        memory_manager=engine.memory_manager,
        onboarding_flow=engine.onboarding_flow,
        onboarding_service=engine.onboarding,
        user_language=None,
    )

    # The short-circuit should return the lesson content (not an LLM reply).
    # Accept either the older "Lesson 1" header or the text-based lesson
    # formatting returned by the dialogue engine.
    assert "Lesson" in resp

    resp = await process_lesson_query(
        user_id=user_id,
        text="what is todays lesson",
        session=session,
        prompt_builder=engine.prompt_builder,
        memory_manager=engine.memory_manager,
        onboarding_flow=engine.onboarding_flow,
        onboarding_service=engine.onboarding,
        user_language=None,
    )

    # The short-circuit should return the full lesson formatting (not a brief
    # LLM reply). Assert we receive a lesson header for lesson 1.
    assert "Lesson 1" in resp
