import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker


def test_rag_list_memories_personal_assistant(monkeypatch):
    # Import inside test to ensure patched symbols resolve correctly
    from src.services.dialogue.command_handlers import parse_rag_prefix, handle_list_memories

    # Create an in-memory engine/session so Session.get_bind() works
    engine = create_engine("sqlite:///:memory:")
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

    # Patch the semantic search service factory used by the handler
    monkeypatch.setattr(
        "src.services.dialogue.command_handlers.get_semantic_search_service",
        lambda: FakeSearchService(),
    )

    # Simulate input that includes the rag prefix
    stripped, is_rag = parse_rag_prefix("rag list memories Personal Assistant")
    assert is_rag is True

    # Call the handler — memory_manager not required for this path
    out = handle_list_memories(stripped, None, session, user_id=1)
    assert out is not None
    assert "Personal Assistant" in out or "Personal Assistant" in out
    assert "note" in out
