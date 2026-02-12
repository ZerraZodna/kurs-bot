import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.database import Base, User
from src.memories import MemoryManager
from src.memories.memory_extractor import MemoryExtractor
from src.services.dialogue.memory_helpers import extract_and_store_memories


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
