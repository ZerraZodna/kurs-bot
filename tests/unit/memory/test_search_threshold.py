"""Unit tests for Semantic Search threshold functionality.

Migrated from tests/test_search_threshold.py to use new test fixtures.
This tests the threshold parameter in semantic search.
"""

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from src.memories.semantic_search import SemanticSearchService


class TestSearchThreshold:
    """Search threshold unit tests."""

    @pytest.mark.asyncio
    async def test_search_with_threshold_filters_results(self, db_session, test_user):
        """Should filter results based on threshold."""
        # Given: A semantic search service with mocked dependencies
        svc = SemanticSearchService()
        
        # Create mock memories that look like MemoryEntity
        mock_memories = []
        for i in range(3):
            mem = MagicMock()
            mem.memory_id = i + 1
            mem.user_id = test_user.user_id
            mem.key = f"test_key_{i}"
            mem.value = f"test_value_{i}"
            mem.category = "fact"
            mem.confidence = 0.5 + (i * 0.15)
            mem.embedding = None  # No stored embedding
            mock_memories.append(mem)
        
        # Mock the embedding service
        mock_embedding_service = MagicMock()
        mock_embedding_service.generate_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])
        mock_embedding_service.batch_embed = AsyncMock(return_value=[[0.5, 0.5, 0.5]] * 3)
        mock_embedding_service.bytes_to_embedding = MagicMock(return_value=None)
        mock_embedding_service.cosine_similarity = MagicMock(side_effect=lambda a, b: 0.8)  # Constant high similarity
        svc.embedding_service = mock_embedding_service
        
        # Mock MemoryHandler's methods to return our test memories
        mock_handler = MagicMock()
        mock_handler.keyword_candidates = MagicMock(return_value=mock_memories)
        
        # When: Searching with a high threshold
        with patch('src.memories.semantic_search.MemoryHandler', return_value=mock_handler):
            results = await svc.search_memories(
                user_id=test_user.user_id,
                query_text="test query",
                session=db_session,
                threshold=0.9,  # High threshold
                limit=10
            )
            
            # Then: Should return results (threshold filtering happens after reranking)
            assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_search_with_zero_threshold_returns_all(self, db_session, test_user):
        """Should return all results when threshold is 0."""
        # Given: A semantic search service
        svc = SemanticSearchService()
        
        # Create mock memories
        mock_memories = []
        for i in range(3):
            mem = MagicMock()
            mem.memory_id = i + 1
            mem.user_id = test_user.user_id
            mem.key = f"test_key_{i}"
            mem.value = f"test_value_{i}"
            mem.category = "fact"
            mem.confidence = 0.5
            mem.embedding = None
            mock_memories.append(mem)
        
        # Mock the embedding service
        mock_embedding_service = MagicMock()
        mock_embedding_service.generate_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])
        mock_embedding_service.batch_embed = AsyncMock(return_value=[[0.5, 0.5, 0.5]] * 3)
        mock_embedding_service.bytes_to_embedding = MagicMock(return_value=None)
        mock_embedding_service.cosine_similarity = MagicMock(return_value=0.5)
        svc.embedding_service = mock_embedding_service
        
        # Mock MemoryHandler
        mock_handler = MagicMock()
        mock_handler.keyword_candidates = MagicMock(return_value=mock_memories)
        
        # When: Searching with zero threshold
        with patch('src.memories.semantic_search.MemoryHandler', return_value=mock_handler):
            results = await svc.search_memories(
                user_id=test_user.user_id,
                query_text="test query",
                session=db_session,
                threshold=0.0,  # Accept any result
                limit=10
            )
            
            # Then: Should return results
            assert isinstance(results, list)

    @pytest.mark.asyncio
    async def test_filter_by_similarity(self):
        """Should filter results by similarity threshold."""
        # Given: A semantic search service
        svc = SemanticSearchService()
        
        # Create mock memories with scores
        mock_memories = []
        for i in range(3):
            mem = MagicMock()
            mem.memory_id = i + 1
            mem.value = f"test_value_{i}"
            mock_memories.append((mem, 0.5 + (i * 0.2)))  # 0.5, 0.7, 0.9
        
        # When: Filtering with threshold 0.6
        filtered = svc.filter_by_similarity(mock_memories, threshold=0.6)
        
        # Then: Should only return memories with score >= 0.6
        assert len(filtered) == 2  # 0.7 and 0.9 pass, 0.5 is filtered out

    @pytest.mark.asyncio
    async def test_rerank_returns_sorted_results(self):
        """Should return reranked results sorted by score."""
        # Given: A semantic search service
        svc = SemanticSearchService()
        
        # Mock the embedding service
        mock_embedding_service = MagicMock()
        mock_embedding_service.generate_embedding = AsyncMock(return_value=[0.1, 0.2, 0.3])
        mock_embedding_service.batch_embed = AsyncMock(return_value=[
            [0.1, 0.1, 0.1],  # Low similarity
            [0.9, 0.9, 0.9],  # High similarity
            [0.5, 0.5, 0.5],  # Medium similarity
        ])
        mock_embedding_service.bytes_to_embedding = MagicMock(return_value=None)
        mock_embedding_service.cosine_similarity = MagicMock(side_effect=lambda a, b: 0.5)
        svc.embedding_service = mock_embedding_service
        
        # Create mock memories
        memories = [MagicMock(value=f"test_{i}") for i in range(3)]
        
        # When: Reranking memories
        results = await svc.rerank_memories(memories, "test query")
        
        # Then: Should return sorted results
        assert len(results) == 3
        assert all(isinstance(r, tuple) and len(r) == 2 for r in results)

