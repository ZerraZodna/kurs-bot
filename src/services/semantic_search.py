"""
Semantic Search Service - Find contextually relevant memories

Uses embeddings to perform semantic similarity search on user memories.
Returns memories ranked by relevance to a query text or embedding.
"""

import logging
from typing import List, Optional, Tuple
from sqlalchemy.orm import Session
from src.models.database import Memory
from src.services.embedding_service import get_embedding_service
from src.config import settings
from src.services.vector_index import VectorIndexClient

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
        categories: Optional[List[str]] = None
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
        
        # Generate embedding for query
        query_embedding = await self.embedding_service.generate_embedding(query_text)
        if query_embedding is None:
            logger.warning(f"Failed to generate embedding for query: {query_text}")
            return []
        
        # Search using embedding
        return await self.search_by_embedding(
            user_id=user_id,
            embedding=query_embedding,
            session=session,
            limit=limit,
            threshold=threshold,
            categories=categories
        )
    
    async def search_by_embedding(
        self,
        user_id: int,
        embedding: List[float],
        session: Session,
        limit: Optional[int] = None,
        threshold: Optional[float] = None,
        categories: Optional[List[str]] = None
    ) -> List[Tuple[Memory, float]]:
        """
        Search for memories similar to given embedding
        
        Args:
            user_id: User ID to search memories for
            embedding: Query embedding vector
            session: Database session
            limit: Maximum results to return
            threshold: Similarity threshold
            categories: Optional list of memory categories to filter by
            
        Returns:
            List of tuples (Memory, similarity_score) sorted by relevance
        """
        if limit is None:
            limit = self.max_results
        if threshold is None:
            threshold = self.similarity_threshold
        # Try vector index first (fast path)
        try:
            idx = VectorIndexClient.from_env()
            candidates = idx.query(embedding, k=limit * 3)
            results = []
            if candidates:
                # Collect ids and fetch corresponding memories
                ids = [int(cid) for cid, _ in candidates if cid.isdigit()]
                query = session.query(Memory).filter(Memory.memory_id.in_(ids)).filter(Memory.user_id == user_id).filter(Memory.is_active == True)
                if categories:
                    query = query.filter(Memory.category.in_(categories))
                mem_map = {m.memory_id: m for m in query.all()}
                # Map back to candidate order and include only above threshold
                for cid, score in candidates:
                    try:
                        mid = int(cid)
                    except Exception:
                        continue
                    mem = mem_map.get(mid)
                    if not mem:
                        continue
                    if score >= threshold:
                        results.append((mem, float(score)))

                # Sort & limit
                results.sort(key=lambda x: x[1], reverse=True)
                return results[:limit]
        except Exception as e:
            logger.debug("Vector index query failed or not configured: %s", e)

        # Fallback: brute-force DB scan and cosine similarity
        query = (
            session.query(Memory)
            .filter(Memory.user_id == user_id)
            .filter(Memory.is_active == True)
            .filter(Memory.embedding.isnot(None))  # Only memories with embeddings
        )
        
        # Filter by categories if provided
        if categories:
            query = query.filter(Memory.category.in_(categories))
        
        memories = query.all()
        
        # Calculate similarities
        results = []
        for memory in memories:
            try:
                # Convert stored bytes back to embedding
                memory_embedding = self.embedding_service.bytes_to_embedding(memory.embedding)
                if memory_embedding is None:
                    logger.warning(f"Failed to deserialize embedding for memory {memory.memory_id}")
                    continue
                
                # Calculate similarity
                similarity = self.embedding_service.cosine_similarity(
                    embedding,
                    memory_embedding
                )
                # Only include if above threshold
                if similarity >= threshold:
                    results.append((memory, similarity))
            
            except Exception as e:
                logger.error(f"Error processing memory {memory.memory_id}: {e}")
                continue
        
        # Sort by similarity (highest first) and limit results
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:limit]
    
    async def rerank_memories(
        self,
        memories: List[Memory],
        query_text: str
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
        
        # Generate query embedding
        query_embedding = await self.embedding_service.generate_embedding(query_text)
        if query_embedding is None:
            return [(m, 0.5) for m in memories]
        
        # Calculate similarities
        results = []
        for memory in memories:
            try:
                if memory.embedding is None:
                    results.append((memory, 0.0))
                    continue
                
                memory_embedding = self.embedding_service.bytes_to_embedding(memory.embedding)
                if memory_embedding is None:
                    results.append((memory, 0.0))
                    continue
                
                similarity = self.embedding_service.cosine_similarity(
                    query_embedding,
                    memory_embedding
                )
                results.append((memory, similarity))
            
            except Exception as e:
                logger.error(f"Error reranking memory {memory.memory_id}: {e}")
                results.append((memory, 0.0))
        
        # Sort by similarity
        results.sort(key=lambda x: x[1], reverse=True)
        return results
    
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
