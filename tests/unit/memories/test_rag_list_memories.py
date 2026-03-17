"""
Migrated tests for RAG list memories.
 migrated from tests/test_rag_list_memories.py
"""
import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.base import Base
from src.models.user import User


def test_rag_list_memories_personal_assistant(monkeypatch):
    """Given: A user asks to list memories with RAG prefix
    When: The RAG command handler processes the request
    Then: It returns the relevant memories
    """
    # Import inside test to ensure patched symbols resolve correctly
    from src.services.dialogue.command_handlers import handle_list_memories, parse_rag_prefix

    # Given: Create an in-memory engine/session
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    # Construct a fake memory-like object (no DB insert required)
    class FakeMemory:
        def __init__(self):
            self.created_at = datetime.datetime(2020, 1, 1, 12, 0)
            self.category = "note"
            self.key = "acim"
            self.value = "Personal Assistant — ACIM commitments and notes."
            self.is_active = True

    mem = FakeMemory()

    class FakeSearchService:
        async def search_memories(self, user_id, query_text, session, limit=20):
            return [(mem, 0.95)]

    # Insert a user row so "User table data" can be included for list output
    user = User(
        user_id=1,
        external_id="ext-1",
        channel="telegram",
        timezone="Europe/Oslo",
        lesson=42,
        first_name="Test",
        last_name="User",
        email="test@example.com",
    )
    session.add(user)
    session.commit()

    # Given: Patch the semantic search service factory
    monkeypatch.setattr(
        "src.services.dialogue.command_handlers.get_semantic_search_service",
        lambda: FakeSearchService(),
    )

    # When: Simulate RAG input with query to trigger semantic search (fixes test)
    stripped, is_rag = parse_rag_prefix("rag list memories acim")
    
    # Then: It should be recognized as RAG
    assert is_rag is True

    # When: Call the handler
    out = handle_list_memories(stripped, None, session, user_id=1)
    
    # Then: It should return the memory
    assert out is not None
    assert "Personal Assistant" in out
    assert "note" in out


def test_list_memories_includes_user_table_data(monkeypatch):
    from src.services.dialogue.command_handlers import handle_list_memories

    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    user = User(
        user_id=7,
        external_id="ext-7",
        channel="telegram",
        timezone="Europe/Oslo",
        lesson=12,
        first_name="Alice",
        last_name="Anderson",
        email="alice@example.com",
    )
    session.add(user)
    session.commit()

    class FakeMemoryHandler:
        def __init__(self, _session):
            self._session = _session

        def list_active_memories(self, user_id, order_ascending=True):
            class FakeMemory:
                def __init__(self):
                    self.created_at = datetime.datetime(2020, 1, 1, 12, 0)
                    self.category = "note"
                    self.key = "acim"
                    self.value = "A memory row"
                    self.is_active = True

            return [FakeMemory()]

    monkeypatch.setattr("src.services.dialogue.command_handlers.MemoryHandler", FakeMemoryHandler)

    out = handle_list_memories("list memories", None, session, user_id=7)

    assert out is not None
    assert "User table data" in out
    assert "user_id=7" in out
    assert "lesson=12" in out
    assert "timezone=Europe/Oslo" in out
