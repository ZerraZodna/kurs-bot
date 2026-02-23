import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.database import Base, User
from src.memories import MemoryManager
from src.memories.memory_extractor import MemoryExtractor
from src.memories.dialogue_helpers import extract_and_store_memories
from src.lessons.state import get_current_lesson


@pytest.fixture(scope="function")
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    # Add a user for FK
    user = User(external_id="99998", channel="telegram", first_name="Test", last_name="User", opted_in=True)
    session.add(user)
    session.commit()
    yield session
    session.close()


@pytest.mark.asyncio
async def test_birthdate_memory_stored(db_session, monkeypatch):
    """Ensure a birthdate fact is stored when extractor returns a birth_date memory."""

    async def fake_call_ollama(prompt, model=None, language=None):
        # Return a JSON response indicating a birth_date memory should be stored
        return '{"memories": [{"store": true, "key": "birth_date", "value": "23.05.1966", "confidence": 0.95, "ttl_hours": null}]}'

    # Patch the Ollama call used by MemoryExtractor
    monkeypatch.setattr("src.services.dialogue.ollama_client.call_ollama", fake_call_ollama)

    mm = MemoryManager(db=db_session)
    user = db_session.query(User).first()

    await extract_and_store_memories(mm, MemoryExtractor, user.user_id, "I am born 23.05.1966")

    memories = mm.get_memory(user.user_id, "birth_date")
    assert len(memories) == 1
    assert "1966" in memories[0]["value"]


@pytest.mark.asyncio
async def test_invalid_lesson_completed_memory_is_skipped(db_session, monkeypatch):
    """Invalid lesson_completed values should not be persisted."""

    async def fake_call_ollama(prompt, model=None, language=None):
        return '{"memories": [{"store": true, "key": "lesson_completed", "value": "current_lesson", "confidence": 0.95, "ttl_hours": null}]}'

    monkeypatch.setattr("src.services.dialogue.ollama_client.call_ollama", fake_call_ollama)

    mm = MemoryManager(db=db_session)
    user = db_session.query(User).first()

    await extract_and_store_memories(mm, MemoryExtractor, user.user_id, "I did not finish it")

    memories = mm.get_memory(user.user_id, "lesson_completed")
    assert memories == []
    assert get_current_lesson(mm, user.user_id) is None


@pytest.mark.asyncio
async def test_valid_lesson_completed_memory_is_normalized_and_applied(db_session, monkeypatch):
    """Valid lesson_completed values should be normalized and update current lesson."""

    async def fake_call_ollama(prompt, model=None, language=None):
        return '{"memories": [{"store": true, "key": "lesson_completed", "value": "lesson 5", "confidence": 0.95, "ttl_hours": null}]}'

    monkeypatch.setattr("src.services.dialogue.ollama_client.call_ollama", fake_call_ollama)

    mm = MemoryManager(db=db_session)
    user = db_session.query(User).first()

    await extract_and_store_memories(mm, MemoryExtractor, user.user_id, "I finished lesson five")

    memories = mm.get_memory(user.user_id, "lesson_completed")
    assert len(memories) == 1
    assert memories[0]["value"] == "5"
    assert get_current_lesson(mm, user.user_id) == 6
