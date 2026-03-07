"""
Test semantic deduplication of memories with different keys/categories.

This tests the scenario from prod where multiple memories exist for the same concept:
- 03-06 preference.preferred_lesson_time=07:30
- 03-07 profile.preferred_lesson_time=08:00  
- 03-07 conversation.preferred_time=08:00

The AI should detect these are all about "preferred lesson time" and only keep ONE.
"""

import pytest
import os
from dataclasses import dataclass
from datetime import datetime, timezone
from typing import Optional

from src.memories.ai_judge import MemoryJudge


@dataclass
class MockMemory:
    """Mock memory for testing."""
    memory_id: int
    key: str
    value: str
    category: str = "fact"
    created_at: Optional[str] = None
    
    def __post_init__(self):
        if self.created_at is None:
            self.created_at = datetime.now(timezone.utc).isoformat()


@pytest.fixture
def judge():
    """Create a MemoryJudge instance for testing."""
    return MemoryJudge()


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("TEST_USE_REAL_OLLAMA", "false").lower() != "true",
    reason="Only runs with real Ollama"
)
async def test_same_key_different_value_conflict(judge):
    """
    Test: User changes preferred_lesson_time from 07:30 to 08:00.
    AI should detect this as a conflict and suggest REPLACE.
    """
    existing = [
        MockMemory(
            memory_id=1,
            key="preferred_lesson_time",
            value="07:30",
            category="preference"
        )
    ]
    
    decision = await judge.evaluate_storage(
        user_id=1,
        proposed_key="preferred_lesson_time",
        proposed_value="08:00",
        user_message="I prefer 08:00 for my lessons",
        existing_memories=existing
    )
    
    print(f"Decision: quality={decision.quality_score}, should_store={decision.should_store}")
    print(f"Conflicts: {decision.conflicts}")
    print(f"Reasoning: {decision.reasoning}")
    
    # Should detect conflict with existing memory
    assert len(decision.conflicts) > 0, "Should detect conflict with existing preferred_lesson_time"
    
    # Should suggest replacing the old value
    conflict = decision.conflicts[0]
    assert conflict.action in ["REPLACE", "MERGE"], f"Should suggest REPLACE or MERGE, got {conflict.action}"
    assert conflict.existing_value == "07:30", "Should reference old value"


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("TEST_USE_REAL_OLLAMA", "false").lower() != "true",
    reason="Only runs with real Ollama"
)
async def test_different_keys_same_concept_conflict(judge):
    """
    Test: User says 'preferred_lesson_time=08:00' but existing memory has
    'preferred_time=07:30' with different key.
    AI should detect these refer to the same concept.
    """
    existing = [
        MockMemory(
            memory_id=1,
            key="preferred_time",
            value="07:30",
            category="conversation"
        )
    ]
    
    decision = await judge.evaluate_storage(
        user_id=1,
        proposed_key="preferred_lesson_time",
        proposed_value="08:00",
        user_message="Actually, I prefer 08:00 for my lessons",
        existing_memories=existing
    )
    
    print(f"Decision: quality={decision.quality_score}, should_store={decision.should_store}")
    print(f"Conflicts: {decision.conflicts}")
    print(f"Reasoning: {decision.reasoning}")
    
    # Should detect semantic conflict even though keys are different
    # (preferred_time vs preferred_lesson_time both refer to lesson time preference)
    assert len(decision.conflicts) > 0, "Should detect semantic conflict between preferred_time and preferred_lesson_time"


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("TEST_USE_REAL_OLLAMA", "false").lower() != "true",
    reason="Only runs with real Ollama"
)
async def test_three_duplicate_memories_scenario(judge):
    """
    Test the exact scenario from prod.db:
    - preference.preferred_lesson_time=07:30
    - profile.preferred_lesson_time=08:00
    - conversation.preferred_time=08:00
    
    When storing a new value, all should be detected as conflicts.
    """
    existing = [
        MockMemory(
            memory_id=1,
            key="preferred_lesson_time",
            value="07:30",
            category="preference"
        ),
        MockMemory(
            memory_id=2,
            key="preferred_lesson_time",
            value="08:00",
            category="profile"
        ),
        MockMemory(
            memory_id=3,
            key="preferred_time",
            value="08:00",
            category="conversation"
        ),
    ]
    
    decision = await judge.evaluate_storage(
        user_id=1,
        proposed_key="preferred_lesson_time",
        proposed_value="09:00",
        user_message="Let me change my lesson time to 09:00",
        existing_memories=existing
    )
    
    print(f"Decision: quality={decision.quality_score}, should_store={decision.should_store}")
    print(f"Conflicts: {[(c.existing_memory_id, c.action, c.existing_value) for c in decision.conflicts]}")
    print(f"Reasoning: {decision.reasoning}")
    
    # Should detect that this is replacing/updating the time preference
    # At minimum should detect conflict with at least one existing memory
    assert len(decision.conflicts) > 0, "Should detect conflict with existing time preferences"


@pytest.mark.asyncio
@pytest.mark.skipif(
    os.getenv("TEST_USE_REAL_OLLAMA", "false").lower() != "true",
    reason="Only runs with real Ollama"
)
async def test_same_value_different_keys_no_conflict(judge):
    """
    Test: User says same time as already stored - should be handled as duplicate/update.
    """
    existing = [
        MockMemory(
            memory_id=1,
            key="preferred_lesson_time",
            value="08:00",
            category="profile"
        )
    ]
    
    decision = await judge.evaluate_storage(
        user_id=1,
        proposed_key="preferred_time",
        proposed_value="08:00",
        user_message="I still prefer 08:00 for lessons",
        existing_memories=existing
    )
    
    print(f"Decision: quality={decision.quality_score}, should_store={decision.should_store}")
    print(f"Conflicts: {decision.conflicts}")
    print(f"Reasoning: {decision.reasoning}")
    
    # Either detects conflict (update) OR validates as same (high quality)
    has_conflict = len(decision.conflicts) > 0
    is_valid = decision.should_store and decision.quality_score >= 0.7
    
    assert has_conflict or is_valid, "Should either detect conflict or validate as same value"


if __name__ == "__main__":
    # Run with: TEST_USE_REAL_OLLAMA=true pytest tests/unit/memories/test_semantic_deduplication.py -v -s
    pytest.main([__file__, "-v", "-s"])

