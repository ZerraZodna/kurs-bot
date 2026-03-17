"""
 Unit tests for _handle_forget_memories in FunctionExecutor.

Tests semantic memory deletion via AI function call.
"""
from typing import List, Tuple
from unittest.mock import AsyncMock, MagicMock, Mock

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.functions.executor import FunctionExecutor
from src.models.base import Base

# No Memory type import needed for mocks


@pytest.mark.asyncio
async def test_handle_forget_memories_success():
    """Test successful memory forgetting with matches found and archived."""
    # Setup in-memory DB
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    # Create executor and context
    executor = FunctionExecutor()
    user_id = 123
    context = {
        "user_id": user_id,
        "session": session,
        "memory_manager": Mock(),
    }

    # Mock semantic search service
    fake_search_service = Mock()
    fake_memories: List[Tuple] = [
        (MagicMock(memory_id=1), 0.95),
        (MagicMock(memory_id=2), 0.90),
        (MagicMock(memory_id=3), 0.85),
    ]
    fake_search_service.search_memories = AsyncMock(return_value=fake_memories)
    
    # Mock the service getter
    with pytest.MonkeyPatch().context() as m:
        m.setattr("src.memories.semantic_search.get_semantic_search_service", lambda: fake_search_service)
        
        # Mock archive_memories to return success count
        context["memory_manager"].archive_memories = Mock(return_value=3)
        
        # Call the handler
        result = await executor._handle_forget_memories(
            params={"query_text": "test query"},
            context=context
        )
    
    # Assertions
    assert result["ok"] is True
    assert result["query_text"] == "test query"
    assert result["found_count"] == 3
    assert result["archived_count"] == 3
    context["memory_manager"].archive_memories.assert_called_once_with(user_id, [1, 2, 3])
    fake_search_service.search_memories.assert_called_once()


@pytest.mark.asyncio
async def test_handle_forget_memories_no_matches():
    """Test when no memories match the query."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    executor = FunctionExecutor()
    context = {
        "user_id": 123,
        "session": session,
        "memory_manager": Mock(),
    }

    fake_search_service = Mock()
    fake_search_service.search_memories = AsyncMock(return_value=[])
    
    with pytest.MonkeyPatch().context() as m:
        m.setattr("src.memories.semantic_search.get_semantic_search_service", lambda: fake_search_service)
        
        result = await executor._handle_forget_memories(
            params={"query_text": "no matches"},
            context=context
        )
    
    assert result["ok"] is False
    assert result["error"] == "No matching memories found"


@pytest.mark.asyncio
async def test_handle_forget_memories_missing_query_text():
    """Test missing required query_text parameter."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    executor = FunctionExecutor()
    context = {
        "user_id": 123,
        "session": session,
        "memory_manager": Mock(),
    }

    result = await executor._handle_forget_memories(
        params={},
        context=context
    )
    
    assert result["ok"] is False
    assert result["error"] == "query_text is required"


@pytest.mark.asyncio
async def test_handle_forget_memories_missing_memory_manager():
    """Test missing memory_manager in context."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    SessionLocal = sessionmaker(bind=engine)
    session = SessionLocal()

    executor = FunctionExecutor()
    context = {
        "user_id": 123,
        "session": session,
        # No memory_manager
    }

    result = await executor._handle_forget_memories(
        params={"query_text": "test"},
        context=context
    )
    
    assert result["ok"] is False
    assert "memory_manager" in result["error"]
