import os
import pytest
from src.triggers.trigger_matcher import get_trigger_matcher


@pytest.mark.skipif(os.getenv("EMBEDDING_BACKEND", "local").lower() == "none", reason="Embeddings disabled")
def test_raw_lesson_trigger_matches_simple():
    """Simpler test: rely on test fixtures (conftest.py) which seed triggers.

    Assert that asking "what is todays lesson" returns at least one
    lesson-related trigger (next_lesson or raw_lesson).
    """
    matcher = get_trigger_matcher()
    # Typical user phrase
    phrase = "what is todays lesson"
    matches = matcher.run(async_fn=matcher.match_triggers, user_text=phrase, top_k=5) if hasattr(matcher, 'run') else None
    # Fallback to calling async match_triggers via event loop for compatibility
    if matches is None:
        import asyncio

        matches = asyncio.run(matcher.match_triggers(phrase, top_k=5))

    assert matches, f"Expected some trigger matches for '{phrase}', got none"
    assert any(m.get("action_type") in ("raw_lesson", "next_lesson") for m in matches), f"Expected lesson-related trigger, got: {matches}"
