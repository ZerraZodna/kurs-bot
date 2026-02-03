"""
Embedding Service - Handles vector embeddings via Ollama

Generates embeddings for memory values using nomic-embed-text model.
Provides utilities for storing and comparing embeddings.
"""

import logging
import numpy as np
import httpx
from typing import List, Optional
from src.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating and managing text embeddings"""
    
    def __init__(self):
        self.embed_url = settings.OLLAMA_EMBED_URL
        self.embed_model = settings.OLLAMA_EMBED_MODEL
        self.embedding_dimension = settings.EMBEDDING_DIMENSION
        self.client = httpx.AsyncClient(timeout=60.0)
    
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
            response = await self.client.post(
                self.embed_url,
                json={
                    "model": self.embed_model,
                    "input": text.strip()
                }
            )
            response.raise_for_status()
            
            data = response.json()
            
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
    
    async def batch_embed(self, texts: List[str]) -> List[Optional[List[float]]]:
        """
        Generate embeddings for multiple texts
        
        Args:
            texts: List of texts to embed
            
        Returns:
            List of embeddings (or None for failures)
        """
        embeddings = []
        for text in texts:
            embedding = await self.generate_embedding(text)
            embeddings.append(embedding)
        return embeddings
    
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
        await self.client.aclose()


# Global instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get or create embedding service singleton"""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service
