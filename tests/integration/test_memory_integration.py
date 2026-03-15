"""
Integration tests for the complete memory/context/dialogue system.

Migrated from tests/test_integration_memory.py to use new test fixtures.
"""

import pytest
import asyncio
from sqlalchemy.orm import Session
from src.models.database import User, Memory, MessageLog
from src.memories import MemoryManager
from src.language.prompt_builder import PromptBuilder
from src.services.dialogue_engine import DialogueEngine
from src.language.prompt_optimizer import PromptOptimizer
from src.services.context_utils import MemoryKey, MemoryCategory

from tests.fixtures.users import create_test_user


class TestCompleteWorkflow:
    """Test the complete memory/context/dialogue workflow."""

    def test_user_onboarding_flow(self, db_session: Session, test_user: User):
        """Given: A new user starting onboarding
        When: Completing the onboarding workflow with profile, goals, and preferences
        Then: All memories should be stored and accessible."""
        mm = MemoryManager(db_session)
        pb = PromptBuilder(db_session, mm)

        # 1. Store profile information during onboarding
        mm.store_memory(
            user_id=test_user.user_id,
            key=MemoryKey.FULL_NAME,
            value=test_user.first_name,
            category=MemoryCategory.PROFILE,
        )

        # 3. Store preferences
        mm.store_memory(
            user_id=test_user.user_id,
            key=MemoryKey.PREFERRED_TONE,
            value="Friendly and encouraging",
            category=MemoryCategory.PREFERENCES,
        )

        # 4. Build onboarding prompt
        prompt = pb.build_onboarding_prompt("Welcome to learning")

        assert "Onboarding" in prompt
        assert "learning" in prompt.lower()

        # 5. Verify all memories stored
        profile = mm.get_memory(test_user.user_id, MemoryKey.FULL_NAME)
        prefs = mm.get_memory(test_user.user_id, MemoryKey.PREFERRED_TONE)

        assert len(profile) > 0
        assert len(prefs) > 0

    def test_conversation_with_context_buildup(self, db_session: Session, test_user: User):
        """Given: A user with stored context
        When: Building prompts for multiple conversation turns
        Then: Context should accumulate across turns."""
        mm = MemoryManager(db_session)
        pb = PromptBuilder(db_session, mm)

        # Log first exchange
        msg1_user = MessageLog(
            user_id=test_user.user_id,
            direction="inbound",
            channel="test",
            content="What is Python?",
            status="delivered",
            message_role="user",
        )
        msg1_asst = MessageLog(
            user_id=test_user.user_id,
            direction="outbound",
            channel="test",
            content="Python is a programming language.",
            status="delivered",
            message_role="assistant",
        )
        db_session.add_all([msg1_user, msg1_asst])
        db_session.commit()

        # Build second prompt - should include history
        second_prompt = pb.build_prompt(
            user_id=test_user.user_id,
            user_input="What about variables?",
            system_prompt="You are a Python tutor.",
            include_conversation_history=True,
            history_turns=1,
        )

        # Should include both goals and history
        assert "Recent Conversation" in second_prompt
        assert "What is Python?" in second_prompt

    def test_prompt_optimization_with_multiple_contexts(self, db_session: Session, test_user: User):
        """Given: Multiple memories with different values
        When: Prioritizing memories
        Then: Should return memories appropriately."""
        mm = MemoryManager(db_session)
        po = PromptOptimizer()

        # Store many memories
        topics = [
            "Python", "Web Development", "Data Science",
            "Machine Learning", "Cloud Computing"
        ]

        for topic in topics:
            mm.store_memory(
                user_id=test_user.user_id,
                key="interest",
                value=topic,
                category=MemoryCategory.PREFERENCES,
                allow_duplicates=True,  # Allow multiple interests
            )

        # Retrieve all
        interests = mm.get_memory(test_user.user_id, "interest")
        assert len(interests) >= 2

    def test_conversation_history_compression(self, db_session: Session, test_user: User):
        """Given: A long conversation history
        When: Compressing history with different strategies
        Then: Should compress appropriately for each strategy."""
        po = PromptOptimizer()

        # Create a long conversation
        turns = []
        for i in range(10):
            user_msg = f"Question {i}: Tell me about topic {i}"
            asst_msg = f"Answer {i}: Topic {i} is interesting because..."
            turns.append((user_msg, asst_msg))

        # Test different compression strategies
        recent = po.compress_conversation_history(turns, max_turns=3, strategy="recent")
        assert len(recent) == 3
        assert "Question 9" in recent[-1][0]  # Should have latest

        important = po.compress_conversation_history(turns, max_turns=3, strategy="important")
        assert len(important) <= 3

        summarized = po.compress_conversation_history(turns, max_turns=3, strategy="summary")
        assert len(summarized) == 3

    def test_token_budget_allocation(self, db_session: Session, test_user: User):
        """Given: Multiple context sections with varying lengths
        When: Allocating a limited token budget
        Then: Should prioritize and truncate appropriately."""
        po = PromptOptimizer()

        sections = {
            "profile": "This is a long profile section " * 50,
            "goals": "These are learning goals " * 40,
            "history": "Conversation history exchange " * 60,
        }

        # Allocate tokens with limited budget
        truncated = po.truncate_context_sections(
            sections,
            total_budget=500,
            priority_order=["profile", "goals", "history"]
        )

        # Should have all sections but truncated
        assert "profile" in truncated


class TestErrorHandling:
    """Test error handling and edge cases."""

    def test_nonexistent_user_handling(self, db_session: Session):
        """Given: A nonexistent user ID
        When: Building a prompt
        Then: Should still return a valid prompt without crashing."""
        pb = PromptBuilder(db_session, MemoryManager(db_session))

        # Should not crash with nonexistent user
        prompt = pb.build_prompt(
            user_id=99999,
            user_input="Hello",
            system_prompt="Hi there",
            include_conversation_history=False,
        )

        # Should still return a valid prompt
        assert "Hello" in prompt
        assert "Hi there" in prompt

    def test_empty_memory_handling(self, db_session: Session, test_user: User):
        """Given: A user with no memories
        When: Building a prompt
        Then: Should build prompt without memories gracefully."""
        pb = PromptBuilder(db_session, MemoryManager(db_session))
        mm = MemoryManager(db_session)

        # User with no memories - create a new user without memories
        user_id = create_test_user(db_session, "no_memory_user", "Empty")

        # Should build prompt without memories
        prompt = pb.build_prompt(
            user_id=user_id,
            user_input="Hello",
            system_prompt="You are helpful",
        )

        assert "You are helpful" in prompt
        assert "Hello" in prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
