"""Embedding service mocking utilities."""

import os
from typing import List, Optional
from unittest.mock import MagicMock, AsyncMock

import pytest


def _get_embedding_dim() -> int:
    """Get embedding dimension from config or environment.
    
    Automatically detects dimension based on EMBEDDING_BACKEND:
    - local: 384 (all-MiniLM-L6-v2)
    - ollama: 768 (embeddinggemma)
    """
    try:
        # Import here to avoid circular imports
        from src.config import settings
        
        # Check if there's an explicit override
        explicit_dim = getattr(settings, "EMBEDDING_DIMENSION", None)
        if explicit_dim:
            return int(explicit_dim)
        
        # Auto-detect based on backend
        backend = getattr(settings, "EMBEDDING_BACKEND", "local").lower()
        if backend == "local":
            return 384
        elif backend == "ollama":
            return 768
        else:
            # Fallback to environment or default
            return int(os.getenv("EMBEDDING_DIMENSION", "384") or 384)
    except Exception:
        # Fallback to environment or default if settings can't be imported
        try:
            return int(os.getenv("EMBEDDING_DIMENSION", "384") or 384)
        except Exception:
            return 384


def create_mock_embedding_service(dim: Optional[int] = None) -> MagicMock:
    """Create a mock embedding service.
    
    Returns a MagicMock that mimics EmbeddingService behavior
    without requiring heavy ML dependencies.
    """
    dim = dim or _get_embedding_dim()
    
    mock_service = MagicMock()
    mock_service.embedding_dimension = dim
    
    async def mock_generate_embedding(text: str) -> Optional[List[float]]:
        if not text:
            return None
        return [0.0] * dim
    
    async def mock_batch_embed(texts: List[str]) -> List[Optional[List[float]]]:
        return [
            None if not t else [0.0] * dim
            for t in texts
        ]
    
    async def mock_close() -> None:
        pass
    
    mock_service.generate_embedding = AsyncMock(side_effect=mock_generate_embedding)
    mock_service.batch_embed = AsyncMock(side_effect=mock_batch_embed)
    mock_service.close = AsyncMock(side_effect=mock_close)
    
    return mock_service


def patch_embedding_service(monkeypatch, dim: Optional[int] = None) -> MagicMock:
    """Patch the embedding service module.
    
    Usage:
        from tests.mocks.embedding_mock import patch_embedding_service
        
        def test_something(monkeypatch):
            mock = patch_embedding_service(monkeypatch)
            # ... test code
    """
    import src.services.embedding_service as emb_module
    
    mock_service = create_mock_embedding_service(dim)
    monkeypatch.setattr(emb_module, "get_embedding_service", lambda: mock_service)
    monkeypatch.setattr(emb_module, "_embedding_service", mock_service)
    
    return mock_service


class EmbeddingMock:
    """Configurable embedding mock for tests.
    
    Usage:
        mock = EmbeddingMock()
        mock.set_embedding("hello", [0.1, 0.2, ...])
        
        with mock.patch():
            result = await generate_embedding("hello")
            assert result == [0.1, 0.2, ...]
    """
    
    def __init__(self, dim: Optional[int] = None):
        self.dim = dim or _get_embedding_dim()
        self._embeddings: dict = {}
        self._default = [0.0] * self.dim
    
    def set_embedding(self, text: str, embedding: List[float]) -> "EmbeddingMock":
        """Set a specific embedding for a text."""
        self._embeddings[text.lower()] = embedding
        return self
    
    def set_default(self, embedding: List[float]) -> "EmbeddingMock":
        """Set the default embedding for unmatched texts."""
        self._default = embedding
        return self
    
    async def _mock_generate(self, text: str) -> Optional[List[float]]:
        if not text:
            return None
        return self._embeddings.get(text.lower(), self._default)
    
    async def _mock_batch(self, texts: List[str]) -> List[Optional[List[float]]]:
        return [await self._mock_generate(t) for t in texts]
    
    def patch(self, monkeypatch):
        """Apply the mock using monkeypatch."""
        import src.services.embedding_service as emb_module
        
        mock_service = MagicMock()
        mock_service.embedding_dimension = self.dim
        mock_service.generate_embedding = AsyncMock(side_effect=self._mock_generate)
        mock_service.batch_embed = AsyncMock(side_effect=self._mock_batch)
        mock_service.close = AsyncMock(return_value=None)
        
        monkeypatch.setattr(emb_module, "get_embedding_service", lambda: mock_service)
        monkeypatch.setattr(emb_module, "_embedding_service", mock_service)
        
        return self


def _get_test_embeddings() -> dict:
    """Get test embeddings with dynamically sized vectors."""
    dim = _get_embedding_dim()
    return {
        "hello": [0.1] * dim,
        "goodbye": [0.2] * dim,
        "yes": [0.3] * dim,
        "no": [0.4] * dim,
        "learn python": [0.5] * dim,
        "daily lesson": [0.6] * dim,
        "reminder": [0.7] * dim,
    }


# Predefined test embeddings for common texts (dynamically sized)
TEST_EMBEDDINGS = _get_test_embeddings()


@pytest.fixture(scope="session")
def test_embeddings():
    """Session-scoped fixture with cached test embeddings."""
    return _get_test_embeddings()
