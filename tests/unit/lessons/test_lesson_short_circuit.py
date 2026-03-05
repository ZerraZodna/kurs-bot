import os
import pytest
import json

from src.models.database import SessionLocal, User, Lesson
from src.services.dialogue_engine import DialogueEngine


@pytest.mark.skipif(os.getenv("EMBEDDING_BACKEND", "local").lower() == "none", reason="Embeddings disabled")
@pytest.mark.skipif(os.getenv("TEST_USE_REAL_OLLAMA", "false").lower() != "true", reason="Only runs with real Ollama")
@pytest.mark.asyncio
@pytest.mark.serial
async def test_todays_lesson_via_ai_function_calling(monkeypatch):
    """
    Test that "todays lesson" queries now go through AI function calling.
    
    Previously, these queries short-circuited directly to lesson content.
    Now they are handled by the AI via the send_todays_lesson function to
    prevent keyword hijacking of complex requests like "remind me about todays lesson".
    """
    # Setup DB objects and mark onboarding complete
    session = SessionLocal()
    from tests.fixtures.users import make_ready_user

    user_id = make_ready_user(session, external_id="u1", first_name="Test")
    # Only add lesson if it doesn't exist
    existing_lesson = session.query(Lesson).filter_by(lesson_id=1).first()
    if not existing_lesson:
        lesson = Lesson(lesson_id=1, title="Lesson 1", content="Lesson 1\nFull lesson text")
        session.add(lesson)
        session.commit()

    engine = DialogueEngine(db=session)

    # Make prompt_builder return today's lesson id
    monkeypatch.setattr(engine.prompt_builder, "get_today_lesson_context", lambda uid: {"state": {"lesson_id": 1}})
    # Skip onboarding for this test
    monkeypatch.setattr(engine.onboarding, "should_show_onboarding", lambda uid: False)

    # Mock the LLM to return a JSON response with send_todays_lesson function call
    # This simulates the AI understanding the request and calling the appropriate function
    async def _mock_llm_with_function(*args, **kwargs):
        return json.dumps({
            "response": "Here's today's lesson for you:",
            "functions": [
                {"name": "send_todays_lesson", "parameters": {}}
            ]
        })

    monkeypatch.setattr("src.services.dialogue.call_ollama", _mock_llm_with_function)
    monkeypatch.setattr("src.services.dialogue.ollama_client.call_ollama", _mock_llm_with_function, raising=False)

    # Test that process_lesson_query returns None for "todays lesson" queries
    # because they should NOT short-circuit - they should go through AI
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

    # process_lesson_query should return None because "todays lesson" is no longer
    # detected as a short-circuit case - it goes through AI function calling
    assert resp is None, "todays lesson should NOT short-circuit - should go through AI"

    resp2 = await process_lesson_query(
        user_id=user_id,
        text="what is todays lesson",
        session=session,
        prompt_builder=engine.prompt_builder,
        memory_manager=engine.memory_manager,
        onboarding_flow=engine.onboarding_flow,
        onboarding_service=engine.onboarding,
        user_language=None,
    )

    # Same for the second query - should return None to let AI handle it
    assert resp2 is None, "todays lesson should NOT short-circuit - should go through AI"


@pytest.mark.skipif(os.getenv("EMBEDDING_BACKEND", "local").lower() == "none", reason="Embeddings disabled")
@pytest.mark.skipif(os.getenv("TEST_USE_REAL_OLLAMA", "false").lower() != "true", reason="Only runs with real Ollama")
@pytest.mark.asyncio
@pytest.mark.serial
async def test_numbered_lesson_still_short_circuits(monkeypatch):
    """
    Test that explicit numbered lessons (e.g., "lesson 5") still short-circuit
    directly to lesson content without calling the LLM.
    """
    # Setup DB objects and mark onboarding complete
    session = SessionLocal()
    from tests.fixtures.users import make_ready_user

    user_id = make_ready_user(session, external_id="u2", first_name="Test")
    # Only add lesson if it doesn't exist
    existing_lesson = session.query(Lesson).filter_by(lesson_id=5).first()
    if not existing_lesson:
        lesson = Lesson(lesson_id=5, title="Lesson 5", content="Lesson 5\nFull lesson text")
        session.add(lesson)
        session.commit()

    engine = DialogueEngine(db=session)

    # Skip onboarding for this test so the short-circuit path runs
    monkeypatch.setattr(engine.onboarding, "should_show_onboarding", lambda uid: False)

    # Ensure we do not call the LLM for this short-circuit path
    async def _llm_fail(*args, **kwargs):
        raise AssertionError("LLM should not be called for explicit numbered lesson short-circuit")

    monkeypatch.setattr("src.services.dialogue.call_ollama", _llm_fail)
    monkeypatch.setattr("src.services.dialogue.ollama_client.call_ollama", _llm_fail, raising=False)

    # Test explicit numbered lesson - should short-circuit
    resp = await process_lesson_query(
        user_id=user_id,
        text="What's lesson 5?",
        session=session,
        prompt_builder=engine.prompt_builder,
        memory_manager=engine.memory_manager,
        onboarding_flow=engine.onboarding_flow,
        onboarding_service=engine.onboarding,
        user_language=None,
    )

    # The short-circuit should return the lesson content (not an LLM reply)
    assert resp is not None, "numbered lesson should short-circuit and return content"
    assert "Lesson 5" in resp

    # Test another variation
    resp2 = await process_lesson_query(
        user_id=user_id,
        text="show me lesson 5",
        session=session,
        prompt_builder=engine.prompt_builder,
        memory_manager=engine.memory_manager,
        onboarding_flow=engine.onboarding_flow,
        onboarding_service=engine.onboarding,
        user_language=None,
    )

    assert resp2 is not None, "numbered lesson should short-circuit and return content"
    assert "Lesson 5" in resp2
