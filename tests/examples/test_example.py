"""Example tests demonstrating best practices for the test suite.

This file serves as a reference for:
- Using the new fixture system
- Writing readable tests with Given-When-Then structure
- Using assertion helpers and builders
- Proper test organization
"""

import pytest
from sqlalchemy.orm import Session

# Import utilities
from tests.utils.assertions import (
    assert_memory_count,
    assert_memory_stored,
    assert_response_contains,
)
from tests.utils.builders import ConversationBuilder, MemoryBuilder, ScheduleBuilder

from src.memories import MemoryManager

# Import fixtures (they're automatically available via conftest.py)
from src.models.database import User


class TestMemoryManager:
    """Example unit tests for MemoryManager using new fixtures."""

    def test_store_memory_creates_active_memory(self, db_session: Session, test_user: User):
        """When storing a memory, it should be created as active."""
        # Given: A memory manager and test user
        mm = MemoryManager(db_session)

        # When: Storing a new memory
        memory_id = mm.store_memory(test_user.user_id, "goal", "Learn Python", category="fact")

        # Then: Memory should exist and be active
        assert memory_id is not None
        assert_memory_stored(db_session, test_user.user_id, "goal", expected_value="Learn Python", category="fact")

    def test_store_memory_with_same_value(self, db_session: Session, test_user: User):
        """When storing same memory value, it should be handled appropriately."""
        # Given: An existing memory
        mm = MemoryManager(db_session)
        mm.store_memory(test_user.user_id, "goal", "Learn Python")

        # When: Storing same value again
        mm.store_memory(test_user.user_id, "goal", "Learn Python")

        # Then: Only one memory should exist (same value merges)
        memories = assert_memory_count(db_session, test_user.user_id, 1, key="goal")

    def test_store_different_value_archives_old_memory(self, db_session: Session, test_user: User):
        """When storing different value, old memory should be archived."""
        # Given: An existing memory
        mm = MemoryManager(db_session)
        mm.store_memory(test_user.user_id, "goal", "Learn Python")

        # When: Storing different value
        mm.store_memory(test_user.user_id, "goal", "Learn SQL")

        # Then: Old memory archived, new one active
        assert_memory_count(db_session, test_user.user_id, 1, key="goal", is_active=True)
        assert_memory_count(db_session, test_user.user_id, 1, key="goal", is_active=False)


class TestMemoryBuilder:
    """Example tests using the MemoryBuilder fluent API."""

    def test_build_memory_with_builder(self, db_session: Session, test_user: User):
        """MemoryBuilder should create memory with specified attributes."""
        # Given-When: Using builder to create memory
        memory = (
            MemoryBuilder(db_session, test_user.user_id)
            .with_key("preference")
            .with_value("morning")
            .with_category("profile")
            .build()
        )

        # Then: Memory created correctly
        assert memory.key == "preference"
        assert memory.value == "morning"
        assert memory.category == "profile"

    def test_build_archived_memory(self, db_session: Session, test_user: User):
        """Builder should support creating archived memories."""
        # When: Creating archived memory
        memory = (
            MemoryBuilder(db_session, test_user.user_id).with_key("old_goal").with_value("Old value").archived().build()
        )

        # Then: Memory should be inactive
        assert not memory.is_active
        assert memory.archived_at is not None

    def test_build_many_memories(self, db_session: Session, test_user: User):
        """Builder should support creating multiple memories."""
        # When: Creating multiple memories
        memories = MemoryBuilder(db_session, test_user.user_id).with_category("test").build_many(5)

        # Then: All memories created
        assert len(memories) == 5
        for i, memory in enumerate(memories):
            assert memory.key == f"test_key_{i}"
            assert memory.category == "test"


class TestScheduleBuilder:
    """Example tests using the ScheduleBuilder fluent API."""

    def test_build_daily_schedule(self, db_session: Session, test_user: User):
        """ScheduleBuilder should create daily schedule."""
        # When: Creating daily schedule at 9 AM
        schedule = ScheduleBuilder(db_session, test_user.user_id).daily().at_time(9, 0).active().build()

        # Then: Schedule created correctly
        assert schedule.schedule_type == "daily"
        assert schedule.cron_expression == "0 0 9 * * *"
        assert schedule.is_active

    def test_build_one_time_schedule(self, db_session: Session, test_user: User):
        """ScheduleBuilder should create one-time schedule."""
        # When: Creating one-time schedule
        schedule = ScheduleBuilder(db_session, test_user.user_id).one_time().send_now().build()

        # Then: Schedule created correctly
        assert schedule.schedule_type == "one_time"
        assert schedule.next_send_time is not None


class TestConversationBuilder:
    """Example tests using the ConversationBuilder fluent API."""

    def test_build_conversation(self, db_session: Session, test_user: User):
        """ConversationBuilder should create multi-turn conversation."""
        # When: Building conversation
        messages = (
            ConversationBuilder(db_session, test_user.user_id)
            .user_says("Hello")
            .bot_responds("Hi there!")
            .user_says("How are you?")
            .bot_responds("I'm doing well!")
            .build()
        )

        # Then: All messages created
        assert len(messages) == 4
        assert messages[0].direction == "inbound"
        assert messages[1].direction == "outbound"


class TestAssertionHelpers:
    """Example tests demonstrating assertion helpers."""

    def test_assert_memory_stored_fails_when_missing(self, db_session: Session, test_user: User):
        """assert_memory_stored should raise when memory missing."""
        with pytest.raises(AssertionError) as exc_info:
            assert_memory_stored(db_session, test_user.user_id, "nonexistent")

        assert "not found" in str(exc_info.value)

    def test_assert_response_contains(self):
        """assert_response_contains should check substrings."""
        response = "Hello! Welcome to the ACIM bot."

        # Should pass
        assert_response_contains(response, "Welcome", "ACIM")

        # Should fail
        with pytest.raises(AssertionError):
            assert_response_contains(response, "Goodbye")


class TestParametrized:
    """Example parametrized tests for multiple scenarios."""

    @pytest.mark.parametrize(
        "time_string,expected_hour,expected_minute",
        [
            ("9:00 AM", 9, 0),
            ("2:30 PM", 14, 30),
            ("21:00", 21, 0),
        ],
    )
    def test_time_parsing(self, time_string, expected_hour, expected_minute):
        """Time parsing should handle various formats."""
        # This is a placeholder - actual implementation would test real parser
        # For demo purposes, just verify parameters work
        assert isinstance(time_string, str)
        assert 0 <= expected_hour <= 23
        assert 0 <= expected_minute <= 59


class TestWithUserFixture:
    """Example tests using different user fixtures."""

    def test_user_fixture_creates_basic_user(self, test_user: User):
        """test_user fixture should create basic user."""
        assert test_user.external_id == "test_user_001"
        assert test_user.first_name == "Test"

    def test_user_with_memories_has_onboarding_data(self, db_session: Session, test_user_with_memories: User):
        """test_user_with_memories should have onboarding memories."""
        mm = MemoryManager(db_session)

        # Should have consent memory
        consent = mm.get_memory(test_user_with_memories.user_id, "data_consent")
        assert consent

    def test_norwegian_user_has_language_set(self, db_session: Session, test_user_norwegian: User):
        """test_user_norwegian should have Norwegian language."""
        mm = MemoryManager(db_session)
        lang = mm.get_memory(test_user_norwegian.user_id, "user_language")
        assert lang
        assert lang[0]["value"] == "no"


# Example of a test class with setup method (for more complex scenarios)
class TestWithSetup:
    """Example tests using setup method for complex initialization."""

    def setup_method(self):
        """Setup runs before each test method."""
        self.test_data = {"key": "value"}

    def test_can_access_setup_data(self):
        """Test should have access to setup data."""
        assert self.test_data["key"] == "value"
