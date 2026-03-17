"""Test the name bug fix - verifies temporal resolution works correctly.

This test verifies that when a user provides a new name (e.g., "Johannes"),
it overrides the old Telegram name (e.g., "Dev").
"""

from datetime import datetime, timezone

import pytest

from src.memories.constants import MemoryCategory, MemoryKey
from src.memories.manager import MemoryManager
from src.memories.topics import MemoryTopic
from src.models.database import Memory, SessionLocal, init_db


@pytest.fixture
def test_user_id():
    """Return a test user ID."""
    return 999990


@pytest.fixture
def clean_test_data(test_user_id):
    """Clean up test data before and after test."""
    db = SessionLocal()
    db.query(Memory).filter(Memory.user_id == test_user_id).delete()
    db.commit()
    yield
    # Cleanup after test
    db.query(Memory).filter(Memory.user_id == test_user_id).delete()
    db.commit()


def test_name_temporal_resolution(clean_test_data, test_user_id):
    """Test that the newest name always wins."""
    init_db()
    mm = MemoryManager()
    tm = mm.topic_manager
    db = SessionLocal()

    # Simulate the bug scenario:
    # 1. First, Telegram provides "Dev" as first_name (older)
    # 2. Then user says "my name is Johannes" (newer)

    # Store old Telegram name first (like from Telegram first_name)
    mm.store_memory(
        user_id=test_user_id,
        key=MemoryKey.FIRST_NAME,
        value="Dev",
        category=MemoryCategory.PROFILE.value,
        source="telegram",
    )

    # Manually set created_at to be older
    mem = (
        db
        .query(Memory)
        .filter(Memory.user_id == test_user_id, Memory.key == MemoryKey.FIRST_NAME, Memory.value == "Dev")
        .first()
    )
    if mem:
        mem.created_at = datetime(2026, 2, 26, 16, 19, 0, tzinfo=timezone.utc)
        db.commit()

    # Store new user-provided name (like from "my name is Johannes")
    mm.store_memory(
        user_id=test_user_id,
        key=MemoryKey.NAME,  # Different key synonym
        value="Johannes",
        category=MemoryCategory.PROFILE.value,
        source="user_conversation",
    )

    # Manually set created_at to be newer
    mem = (
        db
        .query(Memory)
        .filter(Memory.user_id == test_user_id, Memory.key == MemoryKey.NAME, Memory.value == "Johannes")
        .first()
    )
    if mem:
        mem.created_at = datetime(2026, 3, 2, 15, 44, 0, tzinfo=timezone.utc)
        db.commit()

    # Test 1: TopicManager.get_name() should return "Johannes"
    name = tm.get_name(test_user_id)
    assert name == "Johannes", f"Expected 'Johannes' but got '{name}'"

    # Test 2: TopicManager.get_topic() should resolve to "Johannes"
    identity = tm.get_topic(test_user_id, MemoryTopic.IDENTITY)
    assert "name" in identity.fields, "No 'name' field in identity topic"
    resolved_name = identity.fields["name"].current.value
    assert resolved_name == "Johannes", f"Expected 'Johannes' but got '{resolved_name}'"

    # Test 3: Verify both keys are mapped to same canonical field
    assert identity.fields["name"].current.original_key in [MemoryKey.FIRST_NAME, MemoryKey.NAME]
