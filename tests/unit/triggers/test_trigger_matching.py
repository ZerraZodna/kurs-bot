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
class TestTriggerMatching:
    """Test suite for trigger matching behavior."""

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

