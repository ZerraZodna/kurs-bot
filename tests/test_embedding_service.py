"""
Tests for embedding service
"""

import pytest
import numpy as np
from src.services.embedding_service import EmbeddingService
from unittest.mock import AsyncMock, patch, MagicMock


@pytest.fixture
def embedding_service():
    """Create embedding service for testing"""
    return EmbeddingService()


class TestEmbeddingService:
    """Test suite for EmbeddingService"""
    
    @pytest.mark.asyncio
    async def test_generate_embedding_success(self, embedding_service):
        """Test successful embedding generation"""
        mock_response = {
            "embedding": [0.1] * 384,  # 384-dimensional vector
            "model": "nomic-embed-text:latest"
        }
        
        with patch.object(embedding_service.client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value.json.return_value = mock_response
            mock_post.return_value.raise_for_status.return_value = None
            
            embedding = await embedding_service.generate_embedding("test text")
            
            assert embedding is not None
            assert len(embedding) == 384
            assert all(v == 0.1 for v in embedding)
    
    @pytest.mark.asyncio
    async def test_generate_embedding_empty_text(self, embedding_service):
        """Test embedding generation with empty text returns None"""
        embedding = await embedding_service.generate_embedding("")
        assert embedding is None
    
    @pytest.mark.asyncio
    async def test_generate_embedding_connection_error(self, embedding_service):
        """Test embedding generation handles connection errors gracefully"""
        import httpx
        
        with patch.object(embedding_service.client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.side_effect = httpx.ConnectError("Connection failed")
            
            embedding = await embedding_service.generate_embedding("test text")
            
            assert embedding is None
    
    @pytest.mark.asyncio
    async def test_generate_embedding_dimension_mismatch(self, embedding_service):
        """Test embedding generation validates dimension"""
        mock_response = {
            "embedding": [0.1] * 256,  # Wrong dimension
            "model": "nomic-embed-text:latest"
        }
        
        with patch.object(embedding_service.client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value.json.return_value = mock_response
            mock_post.return_value.raise_for_status.return_value = None
            
            embedding = await embedding_service.generate_embedding("test text")
            
            assert embedding is None
    
    def test_cosine_similarity(self, embedding_service):
        """Test cosine similarity calculation"""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [1.0, 0.0, 0.0]
        
        similarity = EmbeddingService.cosine_similarity(vec1, vec2)
        
        assert similarity == pytest.approx(1.0, abs=0.01)
    
    def test_cosine_similarity_orthogonal(self, embedding_service):
        """Test cosine similarity for orthogonal vectors"""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [0.0, 1.0, 0.0]
        
        similarity = EmbeddingService.cosine_similarity(vec1, vec2)
        
        assert similarity == pytest.approx(0.0, abs=0.01)
    
    def test_cosine_similarity_opposite(self, embedding_service):
        """Test cosine similarity for opposite vectors"""
        vec1 = [1.0, 0.0, 0.0]
        vec2 = [-1.0, 0.0, 0.0]
        
        similarity = EmbeddingService.cosine_similarity(vec1, vec2)
        
        assert similarity == pytest.approx(-1.0, abs=0.01)
    
    def test_cosine_similarity_zero_vector(self, embedding_service):
        """Test cosine similarity with zero vector"""
        vec1 = [0.0, 0.0, 0.0]
        vec2 = [1.0, 0.0, 0.0]
        
        similarity = EmbeddingService.cosine_similarity(vec1, vec2)
        
        assert similarity == 0.0
    
    def test_embedding_to_bytes(self, embedding_service):
        """Test embedding to bytes conversion"""
        embedding = [0.1, 0.2, 0.3]
        
        data = EmbeddingService.embedding_to_bytes(embedding)
        
        assert isinstance(data, bytes)
        assert len(data) == len(embedding) * 4  # float32 = 4 bytes each
    
    def test_bytes_to_embedding(self, embedding_service):
        """Test bytes to embedding conversion"""
        original = [0.1, 0.2, 0.3]
        data = EmbeddingService.embedding_to_bytes(original)
        
        recovered = EmbeddingService.bytes_to_embedding(data)
        
        assert recovered is not None
        assert len(recovered) == len(original)
        for o, r in zip(original, recovered):
            assert o == pytest.approx(r, abs=0.001)
    
    def test_bytes_to_embedding_invalid(self, embedding_service):
        """Test bytes to embedding with invalid data"""
        recovered = EmbeddingService.bytes_to_embedding(b"invalid")
        
        assert recovered is None
    
    @pytest.mark.asyncio
    async def test_batch_embed(self, embedding_service):
        """Test batch embedding generation"""
        mock_response = {
            "embedding": [0.1] * 384,
            "model": "nomic-embed-text:latest"
        }
        
        with patch.object(embedding_service.client, 'post', new_callable=AsyncMock) as mock_post:
            mock_post.return_value.json.return_value = mock_response
            mock_post.return_value.raise_for_status.return_value = None
            
            texts = ["text1", "text2", "text3"]
            embeddings = await embedding_service.batch_embed(texts)
            
            assert len(embeddings) == 3
            assert all(e is not None for e in embeddings)
            assert all(len(e) == 384 for e in embeddings if e is not None)
