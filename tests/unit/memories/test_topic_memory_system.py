"""Comprehensive test suite for topic-based memory system."""

import random
from datetime import datetime, timezone

import pytest

from src.memories.constants import MemoryCategory, MemoryKey
from src.memories.manager import MemoryManager
from src.memories.topics import MemoryTopic
from src.models.database import Memory, SessionLocal, init_db


@pytest.fixture
def test_user_id():
    """Return a unique test user ID."""
    return random.randint(900000, 999999)


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


@pytest.fixture
def memory_manager():
    """Return initialized memory manager."""
    init_db()
    return MemoryManager()


def test_all_topics(memory_manager, clean_test_data, test_user_id):
    """Test all memory topics with various keys."""
    mm = memory_manager
    tm = mm.topic_manager

    # Test data for each topic
    test_data = {
        MemoryTopic.IDENTITY: [
            (MemoryKey.FIRST_NAME, "Alice", MemoryCategory.PROFILE.value),
            ("email", "alice@example.com", MemoryCategory.PROFILE.value),
            ("background", "Software engineer", MemoryCategory.PROFILE.value),
        ],
        MemoryTopic.PREFERENCES: [
            (MemoryKey.PREFERRED_LESSON_TIME, "08:00", MemoryCategory.PREFERENCES.value),
            ("timezone", "Europe/Oslo", MemoryCategory.PREFERENCES.value),
        ],
        MemoryTopic.PREFERENCES: [
            ("learning_style", "Visual learner", MemoryCategory.PREFERENCES.value),
            (MemoryKey.USER_LANGUAGE, "en", MemoryCategory.PREFERENCES.value),
        ],
    }

    # Store memories
    for topic, memories in test_data.items():
        for key, value, category in memories:
            mm.store_memory(
                user_id=test_user_id,
                key=key,
                value=value,
                source="test",
                category=category,
            )


def test_edge_cases_no_memories(memory_manager, test_user_id):
    """Test edge case: no memories exist."""
    tm = memory_manager.topic_manager
    name = tm.get_name(test_user_id)
    assert name == "friend", f"Expected 'friend' when no name exists, got '{name}'"


def test_temporal_resolution(memory_manager, clean_test_data, test_user_id):
    """Test temporal resolution with multiple values."""
    mm = memory_manager
    tm = mm.topic_manager
    db = SessionLocal()

    # Store multiple names at different times
    times = [
        ("OldName", datetime(2026, 1, 1, tzinfo=timezone.utc)),
        ("MiddleName", datetime(2026, 2, 1, tzinfo=timezone.utc)),
        ("NewestName", datetime(2026, 3, 1, tzinfo=timezone.utc)),
    ]

    for value, created_at in times:
        mm.store_memory(
            user_id=test_user_id,
            key=MemoryKey.NAME,
            value=value,
            category=MemoryCategory.PROFILE.value,
        )
        # Update created_at
        mem = (
            db.query(Memory)
            .filter(Memory.user_id == test_user_id, Memory.key == MemoryKey.NAME, Memory.value == value)
            .first()
        )
        if mem:
            mem.created_at = created_at
            db.commit()

    name = tm.get_name(test_user_id)
    assert name == "NewestName", f"Expected 'NewestName' but got '{name}'"


def test_keyword_memory(memory_manager, clean_test_data, test_user_id):
    """Test keyword/topic memory - single value that gets updated (no duplicates)."""
    mm = memory_manager
    tm = mm.topic_manager
    db = SessionLocal()

    # Store initial keyword (like AI extracting "meditation" from conversation)
    mm.store_memory(
        user_id=test_user_id,
        key="keyword",  # Single keyword - gets updated like name
        value="meditation",
        category=MemoryCategory.FACT.value,
        source="ai_extraction",
        # allow_duplicates=False by default - prevents conflicting keyword memories
    )

    # Later, user mentions "work stress" - keyword gets UPDATED (not duplicated)
    mm.store_memory(
        user_id=test_user_id,
        key="keyword",
        value="work stress",
        category=MemoryCategory.FACT.value,
        source="ai_extraction",
    )

    # Retrieve keyword - should only have the latest value
    keyword_memories = mm.get_memory(test_user_id, "keyword")
    retrieved = [m["value"] for m in keyword_memories]

    # Should only have ONE value (the latest)
    assert retrieved == ["work stress"], f"Expected ['work stress'] but got {retrieved}"
