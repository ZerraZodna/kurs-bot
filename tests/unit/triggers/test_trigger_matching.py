"""Unit tests for trigger matching behavior.

Refactored to use new test fixtures from tests/fixtures/
"""

import os
import pytest
from sqlalchemy.orm import Session

from src.triggers.trigger_matcher import get_trigger_matcher


@pytest.mark.skipif(
    os.getenv("EMBEDDING_BACKEND", "local").lower() == "none",
    reason="Embeddings disabled"
)
@pytest.mark.serial
class TestTriggerMatching:
    """Test suite for trigger matching behavior."""

    @pytest.fixture(autouse=True)
    def seed_triggers_for_test(self, db_engine, monkeypatch):
        """Seed triggers before each test using the test database engine.
        
        This explicitly seeds triggers in the test class rather than
        relying solely on conftest.py's autouse fixture, ensuring the
        test has the correct trigger data available.
        """
        from scripts.ci_seed_triggers import main as seed_triggers_main
        from sqlalchemy.orm import sessionmaker
        
        # Create a session maker bound to the test engine
        TestSessionLocal = sessionmaker(bind=db_engine, autoflush=False, autocommit=False, future=True)
        
        # Patch SessionLocal in trigger_matcher module so it uses the test DB
        # The module imports SessionLocal at load time, so we need to patch it there too
        monkeypatch.setattr("src.triggers.trigger_matcher.SessionLocal", TestSessionLocal)
        
        # Seed triggers using the test database engine
        seed_triggers_main(engine=db_engine)

    def test_raw_lesson_trigger_matches_simple(self):
        """Should match lesson-related triggers for lesson queries."""
        # Given: A trigger matcher with seeded triggers
        matcher = get_trigger_matcher()
        
        # When: Matching a typical user phrase about today's lesson
        phrase = "what is todays lesson"
        matches = (
            matcher.run(async_fn=matcher.match_triggers, user_text=phrase, top_k=5)
            if hasattr(matcher, 'run') else None
        )
        # Fallback to calling async match_triggers via event loop for compatibility
        if matches is None:
            import asyncio
            matches = asyncio.run(matcher.match_triggers(phrase, top_k=5))

        # Then: Should find lesson-related triggers
        assert matches, f"Expected some trigger matches for '{phrase}', got none"
        assert any(
            m.get("action_type") in ("raw_lesson", "next_lesson")
            for m in matches
        ), f"Expected lesson-related trigger, got: {matches}"

