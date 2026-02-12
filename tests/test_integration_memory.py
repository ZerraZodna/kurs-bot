"""
Integration tests for the complete memory/context/dialogue system
"""

import pytest
import asyncio
from sqlalchemy.orm import Session
from src.models.database import SessionLocal, User, Memory, MessageLog, init_db
from src.memories import MemoryManager
from src.services.prompt_builder import PromptBuilder
from src.services.dialogue_engine import DialogueEngine
from src.services.prompt_optimizer import PromptOptimizer
from src.services.context_utils import MemoryKey, MemoryCategory


@pytest.fixture(scope="module")
def test_db():
    """Module-scoped test database."""
    init_db()
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture
def test_user(test_db: Session):
    """Create a test user."""
    user = User(
        external_id="integration_test_user",
        channel="test",
        first_name="Test",
        last_name="User",
        email="test@example.com",
        opted_in=True,
    )
    test_db.add(user)
    test_db.commit()
    return user


class TestCompleteWorkflow:
    """Test the complete memory/context/dialogue workflow."""
    
    def test_user_onboarding_flow(self, test_db: Session, test_user: User):
        """Test complete onboarding workflow."""
        mm = MemoryManager(test_db)
        pb = PromptBuilder(test_db, mm)
        
        # 1. Store profile information during onboarding
        mm.store_memory(
            user_id=test_user.user_id,
            key=MemoryKey.FULL_NAME,
            value=test_user.first_name,
            category=MemoryCategory.PROFILE,
        )
        
        # 2. Store learning goals
        mm.store_memory(
            user_id=test_user.user_id,
            key=MemoryKey.LEARNING_GOAL,
            value="Master Python basics",
            category=MemoryCategory.GOALS,
            confidence=0.9,
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
        goals = mm.get_memory(test_user.user_id, MemoryKey.LEARNING_GOAL)
        prefs = mm.get_memory(test_user.user_id, MemoryKey.PREFERRED_TONE)
        
        assert len(profile) > 0
        assert len(goals) > 0
        assert len(prefs) > 0
    
    def test_conversation_with_context_buildup(self, test_db: Session, test_user: User):
        """Test conversation where context builds over multiple turns."""
        mm = MemoryManager(test_db)
        pb = PromptBuilder(test_db, mm)
        de = DialogueEngine(test_db, mm)
        
        # Setup user context
        mm.store_memory(
            user_id=test_user.user_id,
            key=MemoryKey.LEARNING_GOAL,
            value="Learn Python",
            category=MemoryCategory.GOALS,
        )
        
        # Simulate first message
        first_prompt = pb.build_prompt(
            user_id=test_user.user_id,
            user_input="What is Python?",
            system_prompt="You are a Python tutor.",
        )
        assert "Learning Goals" in first_prompt
        assert "Python" in first_prompt
        
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
        test_db.add_all([msg1_user, msg1_asst])
        test_db.commit()
        
        # Store progress
        mm.store_memory(
            user_id=test_user.user_id,
            key=MemoryKey.LESSON_COMPLETED,
            value="Python Basics",
            category=MemoryCategory.PROGRESS,
        )
        
        # Build second prompt - should include history
        second_prompt = pb.build_prompt(
            user_id=test_user.user_id,
            user_input="What about variables?",
            system_prompt="You are a Python tutor.",
            include_conversation_history=True,
            history_turns=1,
        )
        
        # Should include both goals and history
        assert "Learning Goals" in second_prompt
        assert "Recent Conversation" in second_prompt
        assert "What is Python?" in second_prompt
    
    def test_memory_conflict_during_conversation(self, test_db: Session, test_user: User):
        """Test that conflicting memories are resolved during conversation."""
        mm = MemoryManager(test_db)
        
        # User initially says they want to learn web dev
        mid1 = mm.store_memory(
            user_id=test_user.user_id,
            key="preferred_topic",
            value="Web development",
            category=MemoryCategory.GOALS,
            confidence=0.8,
        )
        
        # Later changes mind to AI
        mid2 = mm.store_memory(
            user_id=test_user.user_id,
            key="preferred_topic",
            value="Artificial intelligence",
            category=MemoryCategory.GOALS,
            confidence=0.95,
        )
        
        # Should have newer goal active
        memories = mm.get_memory(test_user.user_id, "preferred_topic")
        assert len(memories) == 1
        assert "Artificial intelligence" in memories[0]["value"]
    
    def test_prompt_optimization_with_multiple_contexts(self, test_db: Session, test_user: User):
        """Test prompt optimization when multiple context sources exist."""
        mm = MemoryManager(test_db)
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
                confidence=1.0 - (topics.index(topic) * 0.1),  # Decreasing confidence
                allow_duplicates=True,  # Allow multiple interests
            )
        
        # Retrieve all
        interests = mm.get_memory(test_user.user_id, "interest")
        assert len(interests) > 0
        
        # Prioritize
        prioritized = po.prioritize_memories(interests, max_count=2)
        assert len(prioritized) <= 2
        # Highest confidence should be first
        assert prioritized[0]["confidence"] >= prioritized[1]["confidence"]
    
    def test_conversation_history_compression(self, test_db: Session, test_user: User):
        """Test compression of long conversation histories."""
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
        assert "Question 0" in summarized[0][0]  # Should have first
    
    def test_token_budget_allocation(self, test_db: Session, test_user: User):
        """Test intelligent token budget allocation."""
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
        
        # Total should not exceed budget significantly
        total_tokens = sum(po.estimate_gpt_tokens(text) for text in truncated.values())
        assert total_tokens <= 550  # Small buffer
    
    def test_batch_memory_operations(self, test_db: Session, test_user: User):
        """Test efficient batch memory operations."""
        mm = MemoryManager(test_db)
        
        # Simulate batch onboarding data
        batch_data = [
            ("full_name", "John Doe", "profile"),
            ("learning_goal", "Master Python", "goals"),
            ("contact_frequency", "Daily", "preferences"),
            ("timezone", "EST", "profile"),
        ]
        
        # Store in batch
        memory_ids = []
        for key, value, category in batch_data:
            mid = mm.store_memory(
                user_id=test_user.user_id,
                key=key,
                value=value,
                category=category,
            )
            memory_ids.append(mid)
        
        # Verify all stored
        assert len(memory_ids) == len(batch_data)
        
        # Retrieve specific categories
        profile_memories = test_db.query(Memory).filter(
            Memory.user_id == test_user.user_id,
            Memory.category == "profile",
            Memory.is_active == True,
        ).all()
        
        assert len(profile_memories) == 2  # full_name and timezone
    
    def test_ttl_memory_filtering(self, test_db: Session, test_user: User):
        """Test that TTL memories are properly filtered."""
        from datetime import datetime, timezone, timedelta
        
        mm = MemoryManager(test_db)
        
        # Store persistent memory
        mm.store_memory(
            user_id=test_user.user_id,
            key="permanent_goal",
            value="Learn forever",
            category=MemoryCategory.GOALS,
        )
        
        # Store temporary memory
        mm.store_memory(
            user_id=test_user.user_id,
            key="temporary_state",
            value="Currently learning chapter 3",
            category=MemoryCategory.CONVERSATION,
            ttl_hours=1,
        )
        
        # Both should be retrievable now
        temp = mm.get_memory(test_user.user_id, "temporary_state")
        assert len(temp) > 0
        
        perm = mm.get_memory(test_user.user_id, "permanent_goal")
        assert len(perm) > 0


class TestErrorHandling:
    """Test error handling and edge cases."""
    
    def test_nonexistent_user_handling(self, test_db: Session):
        """Test graceful handling of nonexistent users."""
        pb = PromptBuilder(test_db)
        
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
    
    def test_empty_memory_handling(self, test_db: Session, test_user: User):
        """Test handling of users with no memories."""
        pb = PromptBuilder(test_db)
        mm = MemoryManager(test_db)
        
        # User with no memories
        new_user = User(
            external_id="no_memory_user",
            channel="test",
            first_name="Empty",
            opted_in=True,
        )
        test_db.add(new_user)
        test_db.commit()
        
        # Should build prompt without memories
        prompt = pb.build_prompt(
            user_id=new_user.user_id,
            user_input="Hello",
            system_prompt="You are helpful",
        )
        
        assert "You are helpful" in prompt
        assert "Hello" in prompt


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
