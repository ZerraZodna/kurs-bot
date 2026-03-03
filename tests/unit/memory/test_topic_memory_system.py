"""Comprehensive test suite for topic-based memory system."""

import pytest
import random
from datetime import datetime, timezone, timedelta

from src.models.database import init_db, SessionLocal, Memory
from src.memories.manager import MemoryManager
from src.memories.topic_manager import TopicManager
from src.memories.topics import MemoryTopic, resolve_canonical_key
from src.memories.constants import MemoryCategory


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
            ("first_name", "Alice", MemoryCategory.PROFILE.value),
            ("email", "alice@example.com", MemoryCategory.PROFILE.value),
            ("background", "Software engineer", MemoryCategory.PROFILE.value),
        ],
        MemoryTopic.LESSONS: [
            ("current_lesson", "42", MemoryCategory.PROGRESS.value),
            ("lesson_completed", "41", MemoryCategory.PROGRESS.value),
        ],
        MemoryTopic.SCHEDULE: [
            ("preferred_lesson_time", "08:00", MemoryCategory.PREFERENCE.value),
            ("timezone", "Europe/Oslo", MemoryCategory.PREFERENCE.value),
        ],
        MemoryTopic.GOALS: [
            ("learning_goal", "Complete ACIM course", MemoryCategory.GOALS.value),
            ("acim_commitment", "committed to daily practice", MemoryCategory.GOALS.value),
        ],
        MemoryTopic.PREFERENCES: [
            ("learning_style", "Visual learner", MemoryCategory.PREFERENCES.value),
            ("user_language", "en", MemoryCategory.PREFERENCES.value),
        ],
    }

    # Store memories
    for topic, memories in test_data.items():
        for key, value, category in memories:
            mm.store_memory(
                user_id=test_user_id,
                key=key,
                value=value,
                confidence=0.9,
                source="test",
                category=category,
            )

    # Verify each topic
    for topic in MemoryTopic:
        topic_data = tm.get_topic(test_user_id, topic)

        # Verify expected fields
        if topic in test_data:
            for key, expected_value, _ in test_data[topic]:
                resolved = resolve_canonical_key(key)
                if resolved:
                    _, canonical_field = resolved
                    actual_value = topic_data.get_field_value(canonical_field)
                    assert actual_value == expected_value, \
                        f"Topic {topic.value}: Expected '{expected_value}' but got '{actual_value}'"


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
            key="name",
            value=value,
            category=MemoryCategory.PROFILE.value,
        )
        # Update created_at
        mem = db.query(Memory).filter(
            Memory.user_id == test_user_id,
            Memory.key == "name",
            Memory.value == value
        ).first()
        if mem:
            mem.created_at = created_at
            db.commit()

    name = tm.get_name(test_user_id)
    assert name == "NewestName", f"Expected 'NewestName' but got '{name}'"


def test_ai_context(memory_manager, clean_test_data, test_user_id):
    """Test AI-friendly context generation."""
    mm = memory_manager
    tm = mm.topic_manager

    # Store diverse memories across different topics
    mm.store_memory(test_user_id, "first_name", "Bob", category=MemoryCategory.PROFILE.value)
    mm.store_memory(test_user_id, "current_lesson", "15", category=MemoryCategory.PROGRESS.value)
    mm.store_memory(test_user_id, "learning_goal", "Spiritual growth", category=MemoryCategory.GOALS.value)
    mm.store_memory(test_user_id, "learning_style", "Visual learner", category=MemoryCategory.PREFERENCES.value)

    # Get AI context
    ai_context = tm.get_ai_context(test_user_id)

    # Verify structure
    assert "identity" in ai_context, "identity topic not present"
    assert "name" in ai_context.get("identity", {}), "identity.name not present"
    assert "lessons" in ai_context, "lessons topic not present"
    assert "goals" in ai_context, "goals topic not present"
    assert "preferences" in ai_context, "preferences topic not present"
    assert "learning_style" in ai_context.get("preferences", {}), "preferences.learning_style not present"


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
