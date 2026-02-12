"""
Embedding Service - Handles vector embeddings via Ollama

Generates embeddings for memory values using nomic-embed-text model.
Provides utilities for storing and comparing embeddings.
"""

import logging
import numpy as np
import httpx
import asyncio
from typing import List, Optional
from src.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating and managing text embeddings"""
    
    def __init__(self):
        self.embed_url = settings.OLLAMA_EMBED_URL
        self.embed_model = settings.OLLAMA_EMBED_MODEL
        self.embedding_dimension = settings.EMBEDDING_DIMENSION
        # Client proxy exposes a `post` coroutine so tests can patch it.
        class _ClientProxy:
            async def post(self, *args, **kwargs):
                async with httpx.AsyncClient(timeout=60.0) as client:
                    return await client.post(*args, **kwargs)

        self.client = _ClientProxy()
    
    async def generate_embedding(self, text: str) -> Optional[List[float]]:
        """
        Generate embedding for given text using Ollama
        
        Args:
            text: Text to embed
            
        Returns:
            List of floats representing embedding vector, or None if failed
        """
        if not text or not text.strip():
            logger.warning("Cannot generate embedding for empty text")
            return None
        
        try:
            # Use the client proxy (tests may patch `self.client.post`)
            # Include Authorization header when OLLAMA_API_KEY is configured
            headers = {}
            api_key = getattr(settings, "OLLAMA_API_KEY", None)
            if api_key:
                headers["Authorization"] = f"Bearer {api_key}"

            response = await self.client.post(
                self.embed_url,
                json={
                    "model": self.embed_model,
                    "input": text.strip()
                },
                headers=headers or None,
            )
            # Some test mocks may make `raise_for_status` an async mock.
            _rs = response.raise_for_status()
            if asyncio.iscoroutine(_rs):
                await _rs
            
            data = response.json()
            # In tests/mock contexts `response.json()` may be an async
            # callable (AsyncMock) returning a coroutine. Await if needed.
            if asyncio.iscoroutine(data):
                data = await data
            
            # Handle both single embedding and batch response
            if "embeddings" in data:
                embeddings = data["embeddings"]
                if isinstance(embeddings, list) and len(embeddings) > 0:
                    embedding = embeddings[0]
                else:
                    embedding = embeddings
            else:
                embedding = data.get("embedding")
            
            if embedding is None:
                logger.error(f"No embedding in response: {data}")
                return None
            
            # Convert to list if numpy array
            if isinstance(embedding, np.ndarray):
                embedding = embedding.tolist()
            
            # Validate dimension
            if len(embedding) != self.embedding_dimension:
                logger.error(
                    f"Embedding dimension mismatch: expected {self.embedding_dimension}, "
                    f"got {len(embedding)}"
                )
                return None
            
            return embedding
            
        except httpx.ConnectError as e:
            logger.error(f"Failed to connect to Ollama embed endpoint: {e}")
            return None
        except httpx.HTTPStatusError as e:
            logger.error(f"Ollama embed endpoint returned error: {e}")
            return None
        except Exception as e:
            logger.error(f"Error generating embedding: {e}")
            return None
    
    @staticmethod
    def cosine_similarity(vec1: List[float], vec2: List[float]) -> float:
        """
        Calculate cosine similarity between two vectors
        
        Args:
            vec1: First vector
            vec2: Second vector
            
        Returns:
            Similarity score between -1 and 1 (typically 0 to 1 for normalized vectors)
        """
        try:
            a = np.array(vec1, dtype=np.float32)
            b = np.array(vec2, dtype=np.float32)
            
            # Normalize vectors
            a_norm = np.linalg.norm(a)
            b_norm = np.linalg.norm(b)
            
            if a_norm == 0 or b_norm == 0:
                return 0.0
            
            a = a / a_norm
            b = b / b_norm
            
            # Calculate cosine similarity
            similarity = np.dot(a, b)
            return float(similarity)
        except Exception as e:
            logger.error(f"Error calculating cosine similarity: {e}")
            return 0.0
    
    @staticmethod
    def embedding_to_bytes(embedding: List[float]) -> bytes:
        """
        Convert embedding vector to bytes for storage
        
        Args:
            embedding: List of floats
            
        Returns:
            Bytes representation
        """
        try:
            arr = np.array(embedding, dtype=np.float32)
            return arr.tobytes()
        except Exception as e:
            logger.error(f"Error converting embedding to bytes: {e}")
            return b""
    
    @staticmethod
    def bytes_to_embedding(data: bytes) -> Optional[List[float]]:
        """
        Convert bytes back to embedding vector
        
        Args:
            data: Bytes representation
            
        Returns:
            List of floats or None if failed
        """
        try:
            arr = np.frombuffer(data, dtype=np.float32)
            return arr.tolist()
        except Exception as e:
            logger.error(f"Error converting bytes to embedding: {e}")
            return None
    
    async def close(self):
        """Close HTTP client"""
        if self.client is not None:
            try:
                await self.client.aclose()
            except Exception:
                pass

    async def batch_embed(self, texts: List[str]) -> List[Optional[List[float]]]:
        """Generate embeddings for a batch of texts concurrently.

        Returns a list of embeddings (or None) in the same order as `texts`.
        """
        if not texts:
            return []
        tasks = [self.generate_embedding(t) for t in texts]
        return await asyncio.gather(*tasks)


# Global instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get or create embedding service singleton"""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service

