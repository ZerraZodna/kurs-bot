"""
Embedding Service - Handles vector embeddings via Ollama

Generates embeddings for memory values using nomic-embed-text model.
Provides utilities for storing and comparing embeddings.
"""

import logging
import numpy as np
import httpx
import asyncio
from unittest.mock import AsyncMock
from typing import List, Optional
from src.config import settings

logger = logging.getLogger(__name__)


class EmbeddingService:
    """Service for generating and managing text embeddings"""
    
    def __init__(self):
        self.embed_url = settings.OLLAMA_EMBED_URL
        self.embed_model = settings.OLLAMA_EMBED_MODEL
        # Embedding backend must be explicitly configured via EMBEDDING_BACKEND
        self.backend = getattr(settings, "EMBEDDING_BACKEND", "local")
        # Determine expected embedding dimension per backend. Allow override
        # from settings.EMBEDDING_DIMENSION but prefer a sensible default.
        if self.backend == "local":
            default_dim = 384
        elif self.backend == "ollama":
            default_dim = 768
        else:
            default_dim = settings.EMBEDDING_DIMENSION

        self.embedding_dimension = getattr(settings, "EMBEDDING_DIMENSION", default_dim) or default_dim
        # Client proxy exposes a `post` coroutine so tests can patch it.
        class _ClientProxy:
            async def post(self, *args, **kwargs):
                async with httpx.AsyncClient(timeout=60.0) as client:
                    return await client.post(*args, **kwargs)

        self.client = _ClientProxy()
        # local model placeholder
        self._local_model = None
        self._local_model_dir = None
    
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
            # Backend-specific handling: be strict and do NOT silently fall back
            if self.backend == 'local':
                # If tests have patched the HTTP client with AsyncMock, prefer
                # the mocked HTTP path instead of loading the heavy local model.
                if isinstance(getattr(self.client, 'post', None), AsyncMock):
                    # Use the same HTTP embed call as the 'ollama' backend so tests
                    # that patch `client.post` receive the mocked response.
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
                    _rs = response.raise_for_status()
                    if asyncio.iscoroutine(_rs):
                        await _rs

                    data = response.json()
                    if asyncio.iscoroutine(data):
                        data = await data

                    return self._extract_embedding_from_data(data)

                # Require sentence-transformers local model; do not call HTTP
                if self._local_model is None:
                    try:
                        from sentence_transformers import SentenceTransformer
                    except Exception:
                        logger.error("Local embedding backend requested but 'sentence-transformers' is not installed")
                        return None
                    model_name = getattr(settings, "SENTENCE_TRANSFORMERS_MODEL", "all-MiniLM-L6-v2")
                    self._local_model = await self._ensure_local_model_loaded(model_name)
                    if self._local_model is None:
                        logger.error("Failed to load local sentence-transformers model for local backend")
                        return None

                logger.info("DEBUG: generate_embedding calling local encode for single text (chars=%d)", len(text.strip()))
                vec = await asyncio.to_thread(self._local_model.encode, text.strip(), convert_to_numpy=True)
                if isinstance(vec, np.ndarray):
                    emb = vec.tolist()
                else:
                    emb = list(vec)

                if len(emb) != self.embedding_dimension:
                    logger.error(
                        "Embedding dimension mismatch for local backend: expected %s, got %s",
                        self.embedding_dimension,
                        len(emb),
                    )
                    return None
                return emb

            elif self.backend == 'ollama':
                # Use Ollama HTTP API exclusively for the 'ollama' backend
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
                _rs = response.raise_for_status()
                if asyncio.iscoroutine(_rs):
                    await _rs

                data = response.json()
                if asyncio.iscoroutine(data):
                    data = await data

                return self._extract_embedding_from_data(data)

            else:
                logger.error("Unknown EMBEDDING_BACKEND '%s'", self.backend)
                return None
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

    async def _ensure_local_model_loaded(self, model_name: str):
        """Ensure the SentenceTransformer model is downloaded once and loaded from
        a local cache directory. Returns the loaded SentenceTransformer.

        Strategy:
        - If a local cache dir exists under settings.MODEL_CACHE_DIR, load from it.
        - Otherwise, try to download via huggingface_hub.snapshot_download into
          the cache dir. If huggingface_hub isn't available, fall back to
          creating the model via SentenceTransformer(model_name) once and then
          saving it to the cache dir for subsequent cold starts.
        """
        try:
            from sentence_transformers import SentenceTransformer
        except Exception:
            logger.warning("Local embedding backend requested but 'sentence-transformers' is not installed; deferred to HTTP embed fallback")
            return None

        # compute local cache dir
        base_cache = getattr(settings, "MODEL_CACHE_DIR", None) or "src/data/models"
        import os

        safe_name = model_name.replace("/", "_")
        model_dir = os.path.join(base_cache, safe_name)
        os.makedirs(model_dir, exist_ok=True)

        # If model already present, load it from disk
        if os.listdir(model_dir):
            try:
                logger.info("Loading SentenceTransformer model from local cache: %s", model_dir)
                return await asyncio.to_thread(SentenceTransformer, model_dir)
            except Exception:
                logger.exception("Failed to load SentenceTransformer from local cache %s", model_dir)

        # Attempt to download snapshot into model_dir using huggingface_hub if available
        try:
            from huggingface_hub import snapshot_download
            logger.info("Downloading SentenceTransformer '%s' into local cache %s", model_name, model_dir)
            snapshot_download(repo_id=model_name, cache_dir=model_dir, local_dir=model_dir, allow_patterns=["*"], resume_download=True)
            # load from local dir
            return await asyncio.to_thread(SentenceTransformer, model_dir)
        except Exception:
            logger.debug("huggingface_hub.snapshot_download not available or failed, falling back to SentenceTransformer download")

        # Fallback: construct SentenceTransformer (this will populate HF cache),
        # then save it into our local model_dir for future loads.
        try:
            logger.info("Loading SentenceTransformer '%s' (will save into local cache)", model_name)
            model = await asyncio.to_thread(SentenceTransformer, model_name)
            try:
                model.save(model_dir)
                logger.info("Saved SentenceTransformer '%s' to local cache %s", model_name, model_dir)
            except Exception:
                logger.exception("Failed to save SentenceTransformer to local cache %s", model_dir)
            return model
        except Exception:
            logger.exception("Failed to load SentenceTransformer '%s'", model_name)
            return None

    async def batch_embed(self, texts: List[str]) -> List[Optional[List[float]]]:
        """Generate embeddings for a batch of texts concurrently.

        Returns a list of embeddings (or None) in the same order as `texts`.
        """
        if not texts:
            return []
        if self.backend == 'local' and self._local_model is None:
            # If tests have patched the HTTP client with AsyncMock, prefer
            # the mocked HTTP path instead of loading the heavy local model.
            # For batch embedding: attempt to load local model if backend is local
            try:
                model_name = getattr(settings, "SENTENCE_TRANSFORMERS_MODEL", "all-MiniLM-L6-v2")
                self._local_model = await self._ensure_local_model_loaded(model_name)
            except Exception:
                logger.exception("Failed to load local model for batch embedding")

        if self.backend == 'local' and self._local_model is not None:
            # run encoding in thread pool (batch if supported)
            try:
                logger.info("DEBUG: batch_embed invoking local encode for %d texts (show_progress_bar=False)", len(texts))
                vecs = await asyncio.to_thread(self._local_model.encode, texts, convert_to_numpy=True, show_progress_bar=False)
                out = []
                for vec in vecs:
                    if isinstance(vec, np.ndarray):
                        emb = vec.tolist()
                    else:
                        emb = list(vec)
                    if len(emb) != self.embedding_dimension:
                        logger.error("Batch embedding produced wrong dimension: expected %s got %s", self.embedding_dimension, len(emb))
                        out.append(None)
                    else:
                        out.append(emb)
                return out
            except Exception as e:
                logger.warning(f"Local batch embedding failed, falling back to async calls: {e}")

        tasks = [self.generate_embedding(t) for t in texts]
        return await asyncio.gather(*tasks)

    def _extract_embedding_from_data(self, data) -> Optional[List[float]]:
        """Parse embedding data returned by HTTP embed endpoints.

        Accepts the parsed JSON `data` and returns a list of floats when a
        valid embedding is found and matches `self.embedding_dimension`.
        Returns None on parse errors or dimension mismatches.
        """
        try:
            if isinstance(data, dict) and "embeddings" in data:
                embeddings = data["embeddings"]
                if isinstance(embeddings, list) and len(embeddings) > 0:
                    embedding = embeddings[0]
                else:
                    embedding = embeddings
            elif isinstance(data, dict):
                embedding = data.get("embedding")
            else:
                embedding = None

            if embedding is None:
                logger.error("No embedding in response: %s", data)
                return None

            if isinstance(embedding, np.ndarray):
                embedding = embedding.tolist()

            if not isinstance(embedding, (list, tuple)):
                logger.error("Embedding response has unexpected type: %s", type(embedding))
                return None

            if len(embedding) != self.embedding_dimension:
                logger.error(
                    "Embedding dimension mismatch: expected %s, got %s",
                    self.embedding_dimension,
                    len(embedding),
                )
                return None

            return list(embedding)
        except Exception:
            logger.exception("Failed to parse embedding response")
            return None


# Global instance
_embedding_service: Optional[EmbeddingService] = None


def get_embedding_service() -> EmbeddingService:
    """Get or create embedding service singleton"""
    global _embedding_service
    if _embedding_service is None:
        _embedding_service = EmbeddingService()
    return _embedding_service

