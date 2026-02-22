"""
Semantic Search Service - Find contextually relevant memories

Uses embeddings to perform semantic similarity search on user memories.
Returns memories ranked by relevance to a query text or embedding.
"""

import logging
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from src.models.database import Memory
from src.memories.memory_handler import MemoryHandler
from src.services.embedding_service import get_embedding_service
from src.config import settings

logger = logging.getLogger(__name__)


class SemanticSearchService:
    """Service for semantic search over memory embeddings"""
    
    def __init__(self):
        self.embedding_service = get_embedding_service()
        self.similarity_threshold = settings.SEMANTIC_SEARCH_THRESHOLD
        self.max_results = settings.SEMANTIC_SEARCH_MAX_RESULTS
    
    async def search_memories(
        self,
        user_id: int,
        query_text: str,
        session: Session,
        limit: Optional[int] = None,
        threshold: Optional[float] = None,
        categories: Optional[List[str]] = None,
        query_embedding: Optional[List[float]] = None,
    ) -> List[Tuple[Memory, float]]:
        """
        Search for memories similar to query text
        
        Args:
            user_id: User ID to search memories for
            query_text: Text to search for
            session: Database session
            limit: Maximum results to return (default: SEMANTIC_SEARCH_MAX_RESULTS)
            threshold: Similarity threshold (default: SEMANTIC_SEARCH_THRESHOLD)
            categories: Optional list of memory categories to filter by
            
        Returns:
            List of tuples (Memory, similarity_score) sorted by relevance
        """
        if not query_text or not query_text.strip():
            logger.warning("Cannot search with empty query text")
            return []

        # First: try a simple SQL keyword search (case-insensitive LIKE)
        q = MemoryHandler.build_active_query(session=session, user_id=user_id, categories=categories)

        like_pattern = f"%{query_text.strip()}%"
        try:
            c_q = q.filter(Memory.value.ilike(like_pattern))
            candidates = c_q.all()
            # Sort and cap results in Python to remain compatible with mocked sessions
            candidates.sort(key=lambda m: getattr(m, 'confidence', 0.0), reverse=True)
            candidates = candidates[: ((limit or self.max_results) * 5)]
        except Exception as ex:
            logger.warning(f"Keyword search failed: {ex}")
            candidates = []

        # If we found no candidates via keyword, fall back to scanning a capped set
        if not candidates:
            try:
                candidates = q.all()
                candidates.sort(key=lambda m: getattr(m, 'confidence', 0.0), reverse=True)
                candidates = candidates[:100]
            except Exception as ex:
                logger.warning(f"Fallback memory scan failed: {ex}")
                return []

        # Convert to list of Memory objects and rerank using runtime embeddings
        memories = candidates
        # Rerank will generate embeddings and return scores; keep neutral scores on failure
        try:
            ranked = await self.rerank_memories(memories, query_text, query_embedding=query_embedding)
        except Exception as ex:
            logger.warning(f"Rerank failed: {ex}")
            ranked = [(m, 0.5) for m in memories]

        # Apply threshold and limit
        if threshold is None:
            threshold = self.similarity_threshold

        filtered = [t for t in ranked if t[1] >= threshold]
        filtered.sort(key=lambda t: t[1], reverse=True)
        return filtered[: (limit or self.max_results)]
    
    # search_by_embedding removed: embedding-index based search is not supported.
    
    async def rerank_memories(
        self,
        memories: List[Memory],
        query_text: str,
        query_embedding: Optional[List[float]] = None,
    ) -> List[Tuple[Memory, float]]:
        """
        Rerank a list of memories by relevance to query text
        
        Args:
            memories: List of memories to rerank
            query_text: Query text for ranking
            
        Returns:
            Sorted list of tuples (Memory, similarity_score)
        """
        if not query_text or not query_text.strip():
            # Return in original order with equal scores
            return [(m, 0.5) for m in memories]
        
        # Use provided embedding when available, otherwise generate one now
        if query_embedding is None:
            query_embedding = await self.embedding_service.generate_embedding(query_text)
            if query_embedding is None:
                return [(m, 0.5) for m in memories]

        # Use persisted embedding bytes if available (tests/mocks may provide this).
        mem_embeddings: List[Optional[List[float]]] = []
        to_batch_indices: List[int] = []
        batch_texts: List[str] = []
        for idx, m in enumerate(memories):
            emb_bytes = getattr(m, 'embedding', None)
            if emb_bytes:
                try:
                    emb = self.embedding_service.bytes_to_embedding(emb_bytes)
                except Exception:
                    emb = None
                mem_embeddings.append(emb)
            else:
                mem_embeddings.append(None)
                to_batch_indices.append(idx)
                batch_texts.append(m.value)

        # Batch-embed any memories that don't have stored embeddings
        if to_batch_indices and batch_texts:
            try:
                batch_results = await self.embedding_service.batch_embed(batch_texts)
            except Exception as ex:
                logger.warning(f"Batch embed failed: {ex}")
                batch_results = [None] * len(batch_texts)
            for i, emb in enumerate(batch_results):
                mem_embeddings[to_batch_indices[i]] = emb

        scored: List[Tuple[Memory, float]] = []
        for mem, emb in zip(memories, mem_embeddings):
            if emb is None:
                score = 0.0
            else:
                score = self.embedding_service.cosine_similarity(query_embedding, emb)
            scored.append((mem, score))

        # Return sorted by score descending
        scored.sort(key=lambda t: t[1], reverse=True)
        return scored
    
    def filter_by_similarity(
        self,
        memories_with_scores: List[Tuple[Memory, float]],
        threshold: Optional[float] = None
    ) -> List[Memory]:
        """
        Filter memory results by similarity threshold
        
        Args:
            memories_with_scores: List of (Memory, score) tuples
            threshold: Similarity threshold
            
        Returns:
            Filtered list of Memory objects
        """
        if threshold is None:
            threshold = self.similarity_threshold
        
        return [
            memory for memory, score in memories_with_scores
            if score >= threshold
        ]


# Global instance
_semantic_search_service: Optional[SemanticSearchService] = None


def get_semantic_search_service() -> SemanticSearchService:
    """Get or create semantic search service singleton"""
    global _semantic_search_service
    if _semantic_search_service is None:
        _semantic_search_service = SemanticSearchService()
    return _semantic_search_service
