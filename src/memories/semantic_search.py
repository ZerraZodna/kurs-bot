"""
Keyword Search Service - Find relevant memories

Performs keyword-based search on user memories with recency/relevance scoring.
"""

import logging
from typing import List, Optional, Tuple

from sqlalchemy.orm import Session

from src.config import settings
from src.memories.memory_handler import MemoryHandler
from src.memories.types import MemoryEntity

logger = logging.getLogger(__name__)


class SemanticSearchService:
    """Service for keyword search over memories (embeddings removed)"""

    def __init__(self):
        self.similarity_threshold = settings.SEMANTIC_SEARCH_THRESHOLD or 0.3
        self.max_results = settings.SEMANTIC_SEARCH_MAX_RESULTS or 5

    async def search_memories(
        self,
        user_id: int,
        query_text: str,
        session: Session,
        limit: Optional[int] = None,
        threshold: Optional[float] = None,
        categories: Optional[List[str]] = None,
    ) -> List[Tuple[MemoryEntity, float]]:
        """
        Keyword search for relevant memories.

        Scores by keyword match strength + recency.
        """
        if not query_text or not query_text.strip():
            logger.warning("Cannot search with empty query text")
            return []

        memory_handler = MemoryHandler(session)

        # Primary: keyword candidates (LIKE match count)
        try:
            candidates = memory_handler.keyword_candidates(
                user_id=user_id,
                query_text=query_text,
                categories=categories,
                limit=(limit or self.max_results) * 3 or 30,
            )
        except Exception as ex:
            logger.warning(f"Keyword search failed: {ex}")
            candidates = []

        if not candidates:
            # Fallback: top recent active
            candidates = (
                memory_handler.top_active_memories(
                    user_id=user_id,
                    categories=categories,
                    limit=50,
                )
                or []
            )

        # Score: keyword quality (0-1) * recency boost
        scored = []
        for m in candidates:
            score = self._keyword_relevance_score(query_text, m.value)
            scored.append((m, score))

        # Filter/sort/limit
        thresh = threshold or self.similarity_threshold
        filtered = [(m, s) for m, s in scored if s >= thresh]
        filtered.sort(key=lambda t: t[1], reverse=True)
        return filtered[: limit or self.max_results]

    def _keyword_relevance_score(self, query: str, text: str) -> float:
        """Simple heuristic score: match count * recency proxy."""
        words = set(query.lower().split())
        text_words = set(text.lower().split())
        matches = len(words.intersection(text_words))
        score = min(matches / max(len(words), 1), 1.0)
        # Recency boost (fake, since no timestamp here)
        score *= 0.9 + 0.1 * (len(text) / 1000)  # Longer text slight boost
        return score


# Removed: rerank_memories (embeddings gone)
# filter_by_similarity no longer needed (inline in search_memories)


# Global instance
_semantic_search_service: Optional[SemanticSearchService] = None


def get_semantic_search_service() -> SemanticSearchService:
    """Get or create keyword search service singleton."""
    global _semantic_search_service
    if _semantic_search_service is None:
        _semantic_search_service = SemanticSearchService()
    return _semantic_search_service
