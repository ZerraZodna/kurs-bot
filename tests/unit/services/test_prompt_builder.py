"""
Unit tests for PromptBuilder and context management functionality.

Migrated from tests/test_prompt_builder.py to use new test fixtures.
"""

import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from src.models.database import User, Memory, MessageLog
from src.memories import MemoryManager
from src.language.prompt_builder import PromptBuilder
from src.services.context_utils import ContextOptimizer, MemoryKey, MemoryCategory


@pytest.fixture
def memory_manager(db_session: Session):
    """Create a MemoryManager instance."""
    return MemoryManager(db_session)


@pytest.fixture
def prompt_builder(db_session: Session, memory_manager: MemoryManager):
    """Create a PromptBuilder instance."""
    return PromptBuilder(db_session, memory_manager)


class TestPromptBuilder:
    """Test PromptBuilder functionality."""

    def test_build_basic_prompt(self, prompt_builder: PromptBuilder, test_user: User):
        """Given: Basic system prompt and user input
        When: Building a prompt without context
        Then: Should include system prompt and user input."""
        system_prompt = "You are a helpful assistant."
        user_input = "Hello, how are you?"

        prompt = prompt_builder.build_prompt(
            user_id=test_user.user_id,
            user_input=user_input,
            system_prompt=system_prompt,
            include_conversation_history=False,
        )

        assert system_prompt in prompt
        assert user_input in prompt
        assert "User:" in prompt
        assert "Assistant:" in prompt

    def test_build_prompt_with_profile(self, prompt_builder: PromptBuilder, test_user: User):
        """Given: A test user with profile information
        When: Building a prompt
        Then: Should include user profile information."""
        system_prompt = "You are a tutor."
        user_input = "What's 2+2?"

        prompt = prompt_builder.build_prompt(
            user_id=test_user.user_id,
            user_input=user_input,
            system_prompt=system_prompt,
            include_conversation_history=False,
        )

        assert "User Profile" in prompt
        assert test_user.first_name in prompt
        assert test_user.channel in prompt

    def test_build_prompt_with_goals(self, db_session: Session, prompt_builder: PromptBuilder,
                                    test_user: User, memory_manager: MemoryManager):
        """Given: A user with learning goals stored
        When: Building a prompt
        Then: Should include learning goals in the prompt."""
        # Store a goal
        memory_manager.store_memory(
            user_id=test_user.user_id,
            key=MemoryKey.LEARNING_GOAL,
            value="Learn Python programming",
            confidence=0.95,
            category=MemoryCategory.GOALS,
        )

        prompt = prompt_builder.build_prompt(
            user_id=test_user.user_id,
            user_input="Help me learn",
            system_prompt="You are a teacher.",
            include_conversation_history=False,
        )

        assert "Learning Goals" in prompt
        assert "Python" in prompt

    def test_build_prompt_with_conversation_history(self, db_session: Session,
                                                   prompt_builder: PromptBuilder,
                                                   test_user: User):
        """Given: A user with conversation history
        When: Building a prompt with conversation history
        Then: Should include recent conversation turns."""
        # Add some message history
        for i in range(3):
            user_msg = MessageLog(
                user_id=test_user.user_id,
                direction="inbound",
                channel="telegram",
                content=f"User message {i}",
                status="delivered",
                message_role="user",
            )
            db_session.add(user_msg)

            assistant_msg = MessageLog(
                user_id=test_user.user_id,
                direction="outbound",
                channel="telegram",
                content=f"Assistant response {i}",
                status="delivered",
                message_role="assistant",
            )
            db_session.add(assistant_msg)

        db_session.commit()

        prompt = prompt_builder.build_prompt(
            user_id=test_user.user_id,
            user_input="Continue conversation",
            system_prompt="Be helpful.",
            include_conversation_history=True,
            history_turns=2,
        )

        assert "Recent Conversation" in prompt
        assert "User message" in prompt
        assert "Assistant response" in prompt

    def test_onboarding_prompt(self, prompt_builder: PromptBuilder):
        """Given: A system prompt for onboarding
        When: Building an onboarding prompt
        Then: Should include onboarding-specific guidance."""
        system_prompt = "You are a welcome assistant."

        prompt = prompt_builder.build_onboarding_prompt(system_prompt)

        assert system_prompt in prompt
        assert "Onboarding" in prompt
        assert "name" in prompt.lower()

    def test_build_prompt_includes_telegram_table_guard(self, prompt_builder: PromptBuilder, test_user: User):
        """Given: A telegram user prompt
        When: Building a prompt
        Then: Should include anti-table formatting guidance."""
        prompt = prompt_builder.build_prompt(
            user_id=test_user.user_id,
            user_input="Show me my plans",
            system_prompt="You are a helpful assistant.",
            include_conversation_history=False,
        )

        assert "Output Format Rules" in prompt
        assert "Never use ASCII/Unicode tables" in prompt

    def test_build_rag_prompt_includes_telegram_table_guard(self, prompt_builder: PromptBuilder, test_user: User):
        """Given: A RAG prompt request for telegram
        When: Building a RAG prompt
        Then: Should include anti-table formatting guidance."""
        prompt = prompt_builder.build_rag_prompt(
            user_id=test_user.user_id,
            user_input="Summarize my reminders",
            system_prompt="You are a helpful assistant.",
            include_conversation_history=False,
        )

        assert "Output Format Rules" in prompt
        assert "Never use ASCII/Unicode tables" in prompt

    def test_build_prompt_includes_lesson_text_retrieval_rules_for_direct_lesson_request(
        self, prompt_builder: PromptBuilder, test_user: User
    ):
        """Given: A user request for lesson text
        When: Building a prompt
        Then: Should include lesson text retrieval rules."""
        prompt = prompt_builder.build_prompt(
            user_id=test_user.user_id,
            user_input="Give me lesson text 13",
            system_prompt="You are a helpful assistant.",
            include_conversation_history=False,
        )

        assert "Lesson Text Retrieval Rules" in prompt
        assert "return the lesson text exactly as provided" in prompt.lower()

    def test_build_prompt_omits_lesson_text_retrieval_rules_for_non_lesson_request(
        self, prompt_builder: PromptBuilder, test_user: User
    ):
        """Given: A user request that is not for lesson text
        When: Building a prompt
        Then: Should not include lesson text retrieval rules."""
        prompt = prompt_builder.build_prompt(
            user_id=test_user.user_id,
            user_input="How are you today?",
            system_prompt="You are a helpful assistant.",
            include_conversation_history=False,
        )

        assert "Lesson Text Retrieval Rules" not in prompt


class TestContextOptimizer:
    """Test ContextOptimizer utilities."""

    def test_token_estimation(self):
        """Given: A text string
        When: Estimating token count
        Then: Should return approximate token count."""
        text = "This is a test string."
        tokens = ContextOptimizer.estimate_tokens(text)

        # Rough estimate: 4 chars ≈ 1 token
        expected_approx = len(text) // 4
        assert tokens == expected_approx

    def test_truncate_by_tokens(self):
        """Given: A text string and token limit
        When: Truncating by tokens
        Then: Should return truncated text within limit."""
        text = "This is a longer test string with many words in it."
        max_tokens = 10

        truncated = ContextOptimizer.truncate_by_tokens(text, max_tokens)

        # Truncated text should be shorter
        assert len(truncated) < len(text)
        # Should still be valid
        assert isinstance(truncated, str)

    def test_format_memory_list(self):
        """Given: A list of memories with confidence scores
        When: Formatting for prompt
        Then: Should include values and confidence percentages."""
        memories = [
            {"value": "First goal", "confidence": 1.0},
            {"value": "Second goal", "confidence": 0.8},
            {"value": "Third goal", "confidence": 0.6},
        ]

        formatted = ContextOptimizer.format_memory_list(memories, max_items=3)

        assert "First goal" in formatted
        assert "80%" in formatted  # Confidence for second goal
        assert "60%" in formatted  # Confidence for third goal

    def test_format_memory_list_max_items(self):
        """Given: A list of memories exceeding max_items
        When: Formatting with max_items limit
        Then: Should only include specified number of items."""
        memories = [
            {"value": f"Goal {i}", "confidence": 1.0}
            for i in range(10)
        ]

        formatted = ContextOptimizer.format_memory_list(memories, max_items=3)
        lines = formatted.strip().split("\n")

        assert len(lines) == 3


class TestMemoryIntegration:
    """Test memory manager with prompt builder."""

    def test_memory_categories(self, db_session: Session, memory_manager: MemoryManager, test_user: User):
        """Given: Memories stored in different categories
        When: Retrieving memories
        Then: Should return memories from all categories."""
        categories = [
            (MemoryCategory.PROFILE, MemoryKey.FULL_NAME, "John Doe"),
            (MemoryCategory.GOALS, MemoryKey.LEARNING_GOAL, "Master AI"),
            (MemoryCategory.PREFERENCES, MemoryKey.PREFERRED_TONE, "Professional"),
            (MemoryCategory.PROGRESS, MemoryKey.LESSON_COMPLETED, "Lesson 1"),
        ]

        for category, key, value in categories:
            memory_manager.store_memory(
                user_id=test_user.user_id,
                key=key,
                value=value,
                category=category,
            )

        # Verify retrieval
        for category, key, value in categories:
            memories = memory_manager.get_memory(test_user.user_id, key)
            assert len(memories) > 0
            assert value in memories[0]["value"]

    def test_memory_conflict_resolution(self, memory_manager: MemoryManager, test_user: User):
        """Given: Two memories with the same key but different values
        When: Storing the second memory
        Then: Newer memory should be active."""
        # Store initial memory
        mid1 = memory_manager.store_memory(
            user_id=test_user.user_id,
            key="favorite_color",
            value="blue",
            category="preferences",
        )

        # Store conflicting memory
        mid2 = memory_manager.store_memory(
            user_id=test_user.user_id,
            key="favorite_color",
            value="red",
            category="preferences",
        )

        # Verify conflict handling
        memories = memory_manager.get_memory(test_user.user_id, "favorite_color")

        # Should have the newer one active
        assert len(memories) == 1
        assert memories[0]["value"] == "red"

    def test_memory_with_ttl(self, memory_manager: MemoryManager, test_user: User):
        """Given: A memory with TTL (time-to-live)
        When: Storing the memory
        Then: Memory should be retrievable before expiration."""
        # Store temporary memory
        memory_manager.store_memory(
            user_id=test_user.user_id,
            key="session_state",
            value="active",
            category="conversation",
            ttl_hours=1,  # Expires in 1 hour
        )

        # Should be retrievable
        memories = memory_manager.get_memory(test_user.user_id, "session_state")
        assert len(memories) == 1
        assert memories[0]["value"] == "active"


class TestConversationHistory:
    """Test conversation history tracking."""

    def test_log_conversation_pair(self, db_session: Session, test_user: User):
        """Given: User and assistant messages in a thread
        When: Logging conversation pairs
        Then: Both messages should be persisted."""
        thread_id = "test_thread_123"

        user_msg = MessageLog(
            user_id=test_user.user_id,
            direction="inbound",
            channel="telegram",
            content="Hello assistant",
            status="delivered",
            message_role="user",
            conversation_thread_id=thread_id,
        )
        db_session.add(user_msg)

        assistant_msg = MessageLog(
            user_id=test_user.user_id,
            direction="outbound",
            channel="telegram",
            content="Hello human",
            status="delivered",
            message_role="assistant",
            conversation_thread_id=thread_id,
        )
        db_session.add(assistant_msg)
        db_session.commit()

        # Verify both messages are logged
        messages = db_session.query(MessageLog).filter_by(
            user_id=test_user.user_id,
            conversation_thread_id=thread_id,
        ).all()

        assert len(messages) == 2
        assert messages[0].message_role == "user"
        assert messages[1].message_role == "assistant"

    def test_retrieve_conversation_history(self, db_session: Session, prompt_builder: PromptBuilder, test_user: User):
        """Given: User with message history
        When: Retrieving conversation history
        Then: Should return formatted history."""
        # Log some conversation
        for i in range(3):
            user_msg = MessageLog(
                user_id=test_user.user_id,
                direction="inbound",
                channel="telegram",
                content=f"Message {i}",
                status="delivered",
                message_role="user",
            )
            db_session.add(user_msg)

        db_session.commit()

        # Retrieve history
        history = prompt_builder._build_conversation_history(test_user.user_id, num_turns=2)

        assert "Message" in history


if __name__ == "__main__":
    pytest.main([__file__, "-v"])

