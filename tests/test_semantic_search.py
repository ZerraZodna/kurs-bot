"""
Tests for semantic search service
"""

import pytest
from unittest.mock import AsyncMock, patch, MagicMock
from sqlalchemy.orm import Session
from src.memories.semantic_search import SemanticSearchService
from src.models.database import Memory
from datetime import datetime, timezone


@pytest.fixture
def semantic_search_service():
    """Create semantic search service for testing"""
    return SemanticSearchService()


@pytest.fixture
def mock_memory():
    """Create mock memory object"""
    memory = MagicMock(spec=Memory)
    memory.memory_id = 1
    memory.user_id = 1
    memory.key = "test_key"
    memory.value = "test value"
    memory.category = "profile"
    memory.confidence = 1.0
    memory.is_active = True
    memory.embedding = b"mock_embedding_bytes"
    return memory


@pytest.fixture
def mock_session(mock_memory):
    """Create mock database session"""
    session = MagicMock(spec=Session)
    query_mock = MagicMock()
    query_mock.filter.return_value.filter.return_value.filter.return_value.all.return_value = [mock_memory]
    session.query.return_value = query_mock
    return session


class TestSemanticSearchService:
    """Test suite for SemanticSearchService"""
    
    @pytest.mark.asyncio
    async def test_search_memories_success(self, semantic_search_service, mock_session):
        """Test successful semantic search"""
        with patch.object(
            semantic_search_service.embedding_service,
            'generate_embedding',
            new_callable=AsyncMock
        ) as mock_gen:
            with patch.object(
                semantic_search_service.embedding_service,
                'bytes_to_embedding',
                return_value=[0.1] * 384
            ):
                with patch.object(
                    semantic_search_service.embedding_service,
                    'cosine_similarity',
                    return_value=0.9
                ):
                    mock_gen.return_value = [0.2] * 384
                    
                    results = await semantic_search_service.search_memories(
                        user_id=1,
                        query_text="spiritual guidance",
                        session=mock_session
                    )
                    
                    assert len(results) == 1
                    memory, score = results[0]
                    assert score == 0.9
    
    @pytest.mark.asyncio
    async def test_search_memories_empty_query(self, semantic_search_service, mock_session):
        """
        Tests for semantic search service
        """

        import pytest
        from unittest.mock import AsyncMock, patch, MagicMock
        from sqlalchemy.orm import Session
        from src.memories.semantic_search import SemanticSearchService
        from src.models.database import Memory
        from src.config import settings
        from datetime import datetime, timezone


        @pytest.fixture
        def semantic_search_service():
            """Create semantic search service for testing"""
            return SemanticSearchService()


        @pytest.fixture
        def mock_memory():
            """Create mock memory object"""
            memory = MagicMock(spec=Memory)
            memory.memory_id = 1
            memory.user_id = 1
            memory.key = "test_key"
            memory.value = "test value"
            memory.category = "profile"
            memory.confidence = 1.0
            memory.is_active = True
            memory.embedding = b"mock_embedding_bytes"
            return memory


        @pytest.fixture
        def mock_session(mock_memory):
            """Create mock database session"""
            session = MagicMock(spec=Session)
            query_mock = MagicMock()
            query_mock.filter.return_value.filter.return_value.filter.return_value.all.return_value = [mock_memory]
            session.query.return_value = query_mock
            return session


        class TestSemanticSearchService:
            """Test suite for SemanticSearchService"""
    
            @pytest.mark.asyncio
            async def test_search_memories_success(self, semantic_search_service, mock_session):
                """Test successful semantic search"""
                with patch.object(
                    semantic_search_service.embedding_service,
                    'generate_embedding',
                    new_callable=AsyncMock
                ) as mock_gen:
                    with patch.object(
                        semantic_search_service.embedding_service,
                        'bytes_to_embedding',
                        return_value=[0.1] * settings.EMBEDDING_DIMENSION
                    ):
                        with patch.object(
                            semantic_search_service.embedding_service,
                            'cosine_similarity',
                            return_value=0.9
                        ):
                            mock_gen.return_value = [0.2] * settings.EMBEDDING_DIMENSION
                    
                            results = await semantic_search_service.search_memories(
                                user_id=1,
                                query_text="spiritual guidance",
                                session=mock_session
                            )
                    
                            assert len(results) == 1
                            memory, score = results[0]
                            assert score == 0.9
    
            @pytest.mark.asyncio
            async def test_search_memories_empty_query(self, semantic_search_service, mock_session):
                """Test semantic search with empty query"""
                results = await semantic_search_service.search_memories(
                    user_id=1,
                    query_text="",
                    session=mock_session
                )
        
                assert len(results) == 0
    
            @pytest.mark.asyncio
            async def test_search_memories_embedding_generation_fails(self, semantic_search_service, mock_session):
                """Test semantic search when embedding generation fails"""
                with patch.object(
                    semantic_search_service.embedding_service,
                    'generate_embedding',
                    new_callable=AsyncMock,
                    return_value=None
                ):
                    results = await semantic_search_service.search_memories(
                        user_id=1,
                        query_text="test",
                        session=mock_session
                    )
            
                    assert len(results) == 0
    
            # embedding-index based search tests removed: vector indexing disabled in this branch
    
            @pytest.mark.asyncio
            async def test_rerank_memories(self, semantic_search_service, mock_memory):
                """Test reranking memories by relevance"""
                memories = [mock_memory]
        
                with patch.object(
                    semantic_search_service.embedding_service,
                    'generate_embedding',
                    new_callable=AsyncMock,
                    return_value=[0.2] * settings.EMBEDDING_DIMENSION
                ):
                    with patch.object(
                        semantic_search_service.embedding_service,
                        'bytes_to_embedding',
                        return_value=[0.1] * settings.EMBEDDING_DIMENSION
                    ):
                        with patch.object(
                            semantic_search_service.embedding_service,
                            'cosine_similarity',
                            return_value=0.88
                        ):
                            results = await semantic_search_service.rerank_memories(
                                memories=memories,
                                query_text="test query"
                            )
                    
                            assert len(results) == 1
                            memory, score = results[0]
                            assert score == 0.88
    
            @pytest.mark.asyncio
            async def test_rerank_memories_empty_query(self, semantic_search_service, mock_memory):
                """Test reranking with empty query"""
                memories = [mock_memory]
        
                results = await semantic_search_service.rerank_memories(
                    memories=memories,
                    query_text=""
                )
        
                assert len(results) == 1
                memory, score = results[0]
                assert score == 0.5  # Default score for no query
    
            def test_filter_by_similarity(self, semantic_search_service, mock_memory):
                """Test filtering results by similarity threshold"""
                results_with_scores = [
                    (mock_memory, 0.9),
                    (mock_memory, 0.5),
                    (mock_memory, 0.8),
                ]
        
                filtered = semantic_search_service.filter_by_similarity(
                    results_with_scores,
                    threshold=0.7
                )
        
                assert len(filtered) == 2
    
            @pytest.mark.asyncio
            async def test_search_with_category_filter(self, semantic_search_service):
                """Test search with category filtering"""
                session = MagicMock(spec=Session)
                query_mock = MagicMock()
                session.query.return_value = query_mock
                query_mock.filter.return_value = query_mock
                query_mock.filter.return_value.filter.return_value = query_mock
                query_mock.filter.return_value.filter.return_value.filter.return_value = query_mock
                query_mock.filter.return_value.filter.return_value.filter.return_value.all.return_value = []
        
                with patch.object(
                    semantic_search_service.embedding_service,
                    'generate_embedding',
                    new_callable=AsyncMock,
                    return_value=[0.1] * settings.EMBEDDING_DIMENSION
                ):
                    results = await semantic_search_service.search_memories(
                        user_id=1,
                        query_text="test",
                        session=session,
                        categories=["profile", "goals"]
                    )
            
                    # Query should have been called
                    assert session.query.called
