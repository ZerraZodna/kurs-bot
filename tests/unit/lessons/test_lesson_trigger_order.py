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
async def test_exact_text_keywords_return_raw_lesson(db_session, caplog):
    """Given: User uses exact text keywords
    When: Handling lesson request
    Then: Raw lesson text is returned directly without LLM."""
    caplog.set_level(logging.INFO)
    response = await handle_lesson_request(
        lesson_id=1,
        user_input="What exactly is the exact text of lesson 1?",
        session=db_session,
        user_language="en",
    )
    assert "Lesson 1" in response
    assert "Full lesson text" in response
    # Verify keyword detection path was used
    assert '"matched_action": "raw_lesson"' in caplog.text
    assert '"match_source": "keyword_detection"' in caplog.text


@pytest.mark.asyncio
async def test_no_exact_text_keywords_uses_rag_path(db_session, caplog):
    """Given: User asks about lesson without exact text keywords
    When: Handling lesson request
    Then: RAG/LLM path is used (not raw lesson)."""
    caplog.set_level(logging.INFO)
    
    # Mock the Ollama call to avoid actual LLM invocation
    async def mock_ollama(prompt, memory_manager, user_language):
        return "This is a thoughtful response about the lesson."
    
    import src.lessons.handler as handler_module
    original_call_ollama = handler_module._get_ollama_client
    handler_module._get_ollama_client = lambda: mock_ollama
    
    try:
        response = await handle_lesson_request(
            lesson_id=1,
            user_input="Tell me about lesson 1",  # No exact text keywords
            session=db_session,
            user_language="en",
        )
        # Should get the RAG/LLM response, not raw lesson
        assert "thoughtful response" in response
        # Should NOT have raw lesson logging
        assert '"matched_action": "raw_lesson"' not in caplog.text
    finally:
        handler_module._get_ollama_client = original_call_ollama
