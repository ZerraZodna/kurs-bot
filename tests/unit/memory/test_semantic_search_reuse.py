"""Unit tests for Semantic Search reuse functionality.

Migrated from tests/test_semantic_search_reuse.py to use new test fixtures.
"""

import pytest
from src.memories.semantic_search import SemanticSearchService


class DummyMemory:
    """Dummy memory class for testing."""
    def __init__(self, value, embedding=None):
        self.value = value
        self.embedding = embedding


class TestSemanticSearchReuse:
    """Semantic search reuse unit tests."""

    @pytest.mark.asyncio
    async def test_rerank_uses_provided_embedding(self):
        """Should use provided embedding instead of generating new one."""
        # Given: A semantic search service with a mock embedding service
        svc = SemanticSearchService()

        class MockEmbeddingService:
            async def generate_embedding(self, text):
                # Should NOT be called when a precomputed embedding is provided
                raise RuntimeError("generate_embedding should not be called")

            async def batch_embed(self, texts):
                # Return None for all to simulate missing persisted embeddings
                return [None] * len(texts)

            def bytes_to_embedding(self, b):
                return None

            @staticmethod
            def cosine_similarity(a, b):
                return 0.0

        svc.embedding_service = MockEmbeddingService()

        memories = [DummyMemory("one"), DummyMemory("two")]

        # When: Providing a precomputed query embedding
        # Then: generate_embedding should not be called
        res = await svc.rerank_memories(memories, "query text", query_embedding=[0.1, 0.2, 0.3])
        
        # Then: Should return a valid list of results
        assert isinstance(res, list)
        assert all(isinstance(t, tuple) and len(t) == 2 for t in res)

