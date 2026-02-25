"""
Unit tests for embedding service.

Migrated from tests/test_embedding_service.py to use new test fixtures.
"""

import pytest
import numpy as np
from src.config import settings
from src.services.embedding_service import EmbeddingService
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.fixture
def embedding_service():
    """Create embedding service for testing."""
    return EmbeddingService()


class TestEmbeddingService:
    """Test suite for EmbeddingService."""

    @pytest.mark.asyncio
    async def test_generate_embedding_success(self, embedding_service):
        """Given: A mock successful response from the embedding API
        When: Generating an embedding for a test string
        Then: Should return a valid embedding with correct dimension."""
        mock_response = {
            "embedding": [0.1] * settings.EMBEDDING_DIMENSION,
            "model": "nomic-embed-text:latest"
        }

        with patch.object(embedding_service.client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value.json.return_value = mock_response
            mock_post.return_value.raise_for_status.return_value = None

            embedding = await embedding_service.generate_embedding("test text")

            assert embedding is not None
            assert len(embedding) == settings.EMBEDDING_DIMENSION
            assert all(v == 0.1 for v in embedding)

    @pytest.mark.asyncio
    async def test_generate_embedding_empty_text(self, embedding_service):
        """Given: An empty text string
        When: Generating an embedding
        Then: Should return None."""
        embedding = await embedding_service.generate_embedding("")
        assert embedding is None

    @pytest.mark.asyncio
    async def test_generate_embedding_connection_error(self, embedding_service):
        """Given: A connection error from the embedding API
        When: Generating an embedding
        Then: Should handle gracefully and return None."""
        import httpx

        with patch.object(embedding_service.client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.ConnectError("Connection failed")

            embedding = await embedding_service.generate_embedding("test text")

            assert embedding is None

    @pytest.mark.asyncio
    async def test_generate_embedding_dimension_mismatch(self, embedding_service):
        """Given: An API response with wrong embedding dimension
        When: Generating an embedding
        Then: Should return None."""
        mock_response = {
            "embedding": [0.1] * (settings.EMBEDDING_DIMENSION - 128),  # Wrong dimension
            "model": "nomic-embed-text:latest"
        }

        with patch.object(embedding_service.client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value.json.return_value = mock_response
            mock_post.return_value.raise_for_status.return_value = None

            embedding = await embedding_service.generate_embedding("test text")

            assert embedding is None

    def test_cosine_similarity(self, embedding_service):
        """Given: Two identical vectors
        When: Calculating cosine similarity
        Then: Should return 1.0."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [1.0, 0.0, 0.0]

        similarity = EmbeddingService.cosine_similarity(vec1, vec2)

        assert similarity == pytest.approx(1.0, abs=0.01)

    def test_cosine_similarity_orthogonal(self, embedding_service):
        """Given: Two orthogonal vectors
        When: Calculating cosine similarity
        Then: Should return 0.0."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]

        similarity = EmbeddingService.cosine_similarity(vec1, vec2)

        assert similarity == pytest.approx(0.0, abs=0.01)

    def test_cosine_similarity_opposite(self, embedding_service):
        """Given: Two opposite direction vectors
        When: Calculating cosine similarity
        Then: Should return -1.0."""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [-1.0, 0.0, 0.0]

        similarity = EmbeddingService.cosine_similarity(vec1, vec2)

        assert similarity == pytest.approx(-1.0, abs=0.01)

    def test_cosine_similarity_zero_vector(self, embedding_service):
        """Given: One zero vector
        When: Calculating cosine similarity
        Then: Should return 0.0."""
        vec1 = [0.0, 0.0, 0.0]
        vec2 = [1.0, 0.0, 0.0]

        similarity = EmbeddingService.cosine_similarity(vec1, vec2)

        assert similarity == 0.0

    def test_embedding_to_bytes(self, embedding_service):
        """Given: An embedding list
        When: Converting to bytes
        Then: Should return valid bytes with correct length."""
        embedding = [0.1, 0.2, 0.3]

        data = EmbeddingService.embedding_to_bytes(embedding)

        assert isinstance(data, bytes)
        assert len(data) == len(embedding) * 4  # float32 = 4 bytes each

    def test_bytes_to_embedding(self, embedding_service):
        """Given: Bytes representing an embedding
        When: Converting back to list
        Then: Should recover original values."""
        original = [0.1, 0.2, 0.3]
        data = EmbeddingService.embedding_to_bytes(original)

        recovered = EmbeddingService.bytes_to_embedding(data)

        assert recovered is not None
        assert len(recovered) == len(original)
        for o, r in zip(original, recovered):
            assert o == pytest.approx(r, abs=0.001)

    def test_bytes_to_embedding_invalid(self, embedding_service):
        """Given: Invalid bytes data
        When: Converting to embedding
        Then: Should return None."""
        recovered = EmbeddingService.bytes_to_embedding(b"invalid")

        assert recovered is None

    @pytest.mark.asyncio
    async def test_batch_embed(self, embedding_service):
        """Given: A list of text strings
        When: Batch embedding them
        Then: Should return embeddings for all texts."""
        mock_response = {
            "embedding": [0.1] * settings.EMBEDDING_DIMENSION,
            "model": "nomic-embed-text:latest"
        }

        with patch.object(embedding_service.client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value.json.return_value = mock_response
            mock_post.return_value.raise_for_status.return_value = None

            texts = ["text1", "text2", "text3"]
            embeddings = await embedding_service.batch_embed(texts)

            assert len(embeddings) == 3
            assert all(e is not None for e in embeddings)
            assert all(len(e) == settings.EMBEDDING_DIMENSION for e in embeddings if e is not None)

