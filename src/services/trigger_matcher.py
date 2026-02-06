import time
import logging
from typing import List, Dict, Optional

from src.models.database import SessionLocal, TriggerEmbedding
from src.services.embedding_service import get_embedding_service
from src.config import settings

logger = logging.getLogger(__name__)


class TriggerMatcher:
    """Loads trigger embeddings from DB and matches incoming text."""

    def __init__(self, refresh_secs: Optional[int] = None):
        self.refresh_secs = refresh_secs or settings.TRIGGER_MATCHER_REFRESH_SECS
        self._loaded_at = 0.0
        self._triggers: List[Dict] = []
        self.embedding_service = get_embedding_service()

    def _load_triggers(self):
        now = time.time()
        if self._triggers and (now - self._loaded_at) < self.refresh_secs:
            return

        db = SessionLocal()
        try:
            rows = db.query(TriggerEmbedding).all()
            results = []
            for r in rows:
                results.append({
                    "trigger_id": r.id,
                    "name": r.name,
                    "action_type": r.action_type,
                    "embedding": r.embedding,
                    "threshold": float(r.threshold or settings.TRIGGER_SIMILARITY_THRESHOLD),
                })
            self._triggers = results
            self._loaded_at = now
            logger.debug(f"Loaded {len(self._triggers)} triggers for matcher")
        finally:
            db.close()

    async def match_triggers(self, user_text: str, top_k: int = 3) -> List[Dict]:
        """Match triggers for the provided text and return top_k matches.

        Returns list of dicts: {trigger_id, name, action_type, score, threshold}
        """
        if not user_text or not user_text.strip():
            return []

        self._load_triggers()

        if not self._triggers:
            return []

        embedding = await self.embedding_service.generate_embedding(user_text)
        if not embedding:
            return []

        matches: List[Dict] = []
        for t in self._triggers:
            # Convert stored bytes to embedding
            try:
                stored = self.embedding_service.bytes_to_embedding(t["embedding"]) if t.get("embedding") else None
            except Exception:
                stored = None

            if not stored:
                continue

            score = self.embedding_service.cosine_similarity(embedding, stored)
            matches.append({
                "trigger_id": t["trigger_id"],
                "name": t["name"],
                "action_type": t["action_type"],
                "score": float(score),
                "threshold": float(t.get("threshold", settings.TRIGGER_SIMILARITY_THRESHOLD)),
            })

        # Sort by score desc and return top_k
        matches.sort(key=lambda x: x["score"], reverse=True)
        return matches[:top_k]


# Module-level singleton
_matcher: Optional[TriggerMatcher] = None


def get_trigger_matcher() -> TriggerMatcher:
    global _matcher
    if _matcher is None:
        _matcher = TriggerMatcher()
    return _matcher
