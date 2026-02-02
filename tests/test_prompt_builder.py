"""
Tests for PromptBuilder and context management functionality
"""

import pytest
from datetime import datetime, timezone, timedelta
from sqlalchemy.orm import Session
from src.models.database import SessionLocal, User, Memory, MessageLog, init_db
from src.services.memory_manager import MemoryManager
from src.services.prompt_builder import PromptBuilder
from src.services.context_utils import ContextOptimizer, MemoryKey, MemoryCategory


@pytest.fixture
def db_session():
    """Create a test database session."""
    init_db()
    db = SessionLocal()
    yield db
    db.close()


@pytest.fixture
def test_user(db_session: Session):
    """Create a test user."""
    user = User(
        external_id="test_user_1",
        channel="telegram",
        first_name="Test",
        last_name="User",
        email="test@example.com",
        opted_in=True,
    )
    db_session.add(user)
    db_session.commit()
    return user


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
        """Test basic prompt building without context."""
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
        """Test prompt building includes user profile."""
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
        """Test prompt includes learning goals."""
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
        """Test prompt includes recent conversation history."""
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
        """Test onboarding prompt generation."""
        system_prompt = "You are a welcome assistant."
        
        prompt = prompt_builder.build_onboarding_prompt(system_prompt)
        
        assert system_prompt in prompt
        assert "Onboarding" in prompt
        assert "name" in prompt.lower()


class TestContextOptimizer:
    """Test ContextOptimizer utilities."""
    
    def test_token_estimation(self):
        """Test rough token count estimation."""
        text = "This is a test string."
        tokens = ContextOptimizer.estimate_tokens(text)
        
        # Rough estimate: 4 chars ≈ 1 token
        expected_approx = len(text) // 4
        assert tokens == expected_approx
    
    def test_truncate_by_tokens(self):
        """Test text truncation by token limit."""
        text = "This is a longer test string with many words in it."
        max_tokens = 10
        
        truncated = ContextOptimizer.truncate_by_tokens(text, max_tokens)
        
        # Truncated text should be shorter
        assert len(truncated) < len(text)
        # Should still be valid
        assert isinstance(truncated, str)
    
    def test_format_memory_list(self):
        """Test formatting memory lists for prompts."""
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
        """Test max_items limit in memory list formatting."""
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
        """Test storing memories in different categories."""
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
        """Test that conflicting memories are handled properly."""
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
        """Test memory TTL (time-to-live) functionality."""
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
        """Test logging user/assistant message pair."""
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
        """Test retrieving conversation history for context."""
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
