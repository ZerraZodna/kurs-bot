"""Unit tests for trigger matcher.

Refactored to use new test fixtures from tests/fixtures/
"""

import asyncio
import pytest
from sqlalchemy.orm import Session

from src.triggers.trigger_matcher import TriggerMatcher
from src.models.database import TriggerEmbedding


class DummyEmbedSvc:
    """Mock embedding service for deterministic testing."""
    
    def __init__(self, dim=4):
        self.dim = dim

    async def generate_embedding(self, text: str):
        # deterministic mapping based on seed trigger wording
        t = (text or "").lower()
        # map reminder-like queries to the first vector
        if "remind" in t or "reminder" in t or "reminders" in t:
            return [1.0, 0.0, 0.0, 0.0]
        # map RAG-related utterances to the second vector
        if "rag" in t or "use rag" in t or "stop using rag" in t:
            return [0.0, 1.0, 0.0, 0.0]
        # default
        return [0.0, 0.0, 1.0, 0.0]

    def embedding_to_bytes(self, emb):
        import numpy as np
        return np.array(emb, dtype='float32').tobytes()

    def bytes_to_embedding(self, data):
        import numpy as np
        return np.frombuffer(data, dtype='float32').tolist()

    def cosine_similarity(self, a, b):
        import numpy as np
        a = np.array(a); b = np.array(b)
        if a.sum() == 0 or b.sum() == 0:
            return 0.0
        return float((a / (np.linalg.norm(a))) @ (b / (np.linalg.norm(b))))


#@pytest.mark.serial
class TestTriggerMatcher:
    """Test suite for TriggerMatcher."""

    @pytest.fixture(autouse=True)
    def seed_triggers_for_test(self, db_engine, monkeypatch):
        """Patch SessionLocal in trigger_matcher to use test DB.
        
        The TriggerMatcher module imports SessionLocal at load time, so we
        need to patch it there to ensure it uses the test database.
        """
        from sqlalchemy.orm import sessionmaker
        
        # Create a session maker bound to the test engine
        TestSessionLocal = sessionmaker(bind=db_engine, autoflush=False, autocommit=False, future=True)
        
        # Patch SessionLocal in trigger_matcher module so it uses the test DB
        monkeypatch.setattr("src.triggers.trigger_matcher.SessionLocal", TestSessionLocal)

    @pytest.mark.asyncio
    async def test_matcher_prefers_closest(self, db_session: Session):
        """Should match closest trigger based on embedding similarity."""
        from src.triggers.trigger_matcher import refresh_trigger_matcher_cache
        
        # Given: A mock embedding service and two seed triggers
        svc = DummyEmbedSvc()
        
        # Clear existing triggers to make the test deterministic
        db_session.query(TriggerEmbedding).delete()
        db_session.commit()

        t1 = TriggerEmbedding(
            name="create_schedule",
            action_type="create_schedule",
            embedding=svc.embedding_to_bytes([1, 0, 0, 0]),
            threshold=0.5
        )
        t2 = TriggerEmbedding(
            name="enter_rag",
            action_type="enter_rag",
            embedding=svc.embedding_to_bytes([0, 1, 0, 0]),
            threshold=0.5
        )
        db_session.add(t1)
        db_session.add(t2)
        db_session.commit()

        # And: A trigger matcher with the mock service
        matcher = TriggerMatcher()
        matcher.embedding_service = svc
        # force reload
        matcher._loaded_at = 0
        # Also refresh the module-level cache to pick up the patched SessionLocal
        refresh_trigger_matcher_cache()

        # When: Matching triggers for a reminder query
        matches = await matcher.match_triggers(
            "Please remind me every day", top_k=2
        )

        # Then: Should find matches and prefer the closest one
        assert matches
        assert matches[0]["name"] == "create_schedule"
        assert matches[0]["score"] > matches[1]["score"]

