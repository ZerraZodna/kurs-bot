#!/usr/bin/env python3
"""Test script for AI Memory Judge."""

import sys
import asyncio
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

from src.memories.ai_judge import MemoryJudge, StorageDecision


class MockMemory:
    """Mock memory object for testing."""
    def __init__(self, memory_id, key, value, created_at=None):
        self.memory_id = memory_id
        self.key = key
        self.value = value
        self.created_at = created_at or "2024-01-01"


async def test_ai_judge():
    """Test the AI judge with sample scenarios."""
    
    judge = MemoryJudge()
    
    print("=" * 60)
    print("Testing AI Memory Judge")
    print("=" * 60)
    
    # Test 1: Corrupted name value
    print("\n1. Testing corrupted name value...")
    existing = []
    decision = await judge.evaluate_storage(
        user_id=1,
        proposed_key="first_name",
        proposed_value="No, my full name is spelled backwards sennahoJ",
        user_message="No, my full name is spelled backwards sennahoJ",
        existing_memories=existing
    )
    print(f"   Quality score: {decision.quality_score}")
    print(f"   Should store: {decision.should_store}")
    print(f"   Cleaned value: {decision.cleaned_value}")
    print(f"   Issues: {decision.issues}")
    print(f"   Reasoning: {decision.reasoning[:100]}...")
    
    # Test 2: Duplicate name detection
    print("\n2. Testing duplicate name detection...")
    existing = [MockMemory(1, "first_name", "Johannes")]
    decision = await judge.evaluate_storage(
        user_id=1,
        proposed_key="name",
        proposed_value="sennahoJ",
        user_message="My name is sennahoJ",
        existing_memories=existing
    )
    print(f"   Quality score: {decision.quality_score}")
    print(f"   Conflicts found: {len(decision.conflicts)}")
    for c in decision.conflicts:
        print(f"   - Conflict with ID {c.existing_memory_id}: {c.action}")
        print(f"     Reason: {c.reason}")
    
    # Test 3: Valid independent memory
    print("\n3. Testing valid independent memory...")
    existing = [MockMemory(1, "first_name", "Johannes")]
    decision = await judge.evaluate_storage(
        user_id=1,
        proposed_key="preferred_lesson_time",
        proposed_value="morning",
        user_message="I prefer to study in the morning",
        existing_memories=existing
    )
    print(f"   Quality score: {decision.quality_score}")
    print(f"   Should store: {decision.should_store}")
    print(f"   Conflicts: {len(decision.conflicts)}")
    
    # Test 4: Email update (should replace old)
    print("\n4. Testing email update...")
    existing = [MockMemory(1, "email", "old@example.com")]
    decision = await judge.evaluate_storage(
        user_id=1,
        proposed_key="email",
        proposed_value="new@example.com",
        user_message="My new email is new@example.com",
        existing_memories=existing
    )
    print(f"   Quality score: {decision.quality_score}")
    print(f"   Conflicts: {len(decision.conflicts)}")
    for c in decision.conflicts:
        print(f"   - Action: {c.action}")
    
    print("\n" + "=" * 60)
    print("Tests complete!")
    print("=" * 60)


if __name__ == "__main__":
    asyncio.run(test_ai_judge())
