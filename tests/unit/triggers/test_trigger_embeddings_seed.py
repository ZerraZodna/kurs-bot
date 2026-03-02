"""
Unit tests for Trigger Embeddings Seed.

Migrated from tests/test_trigger_embeddings_seed.py to use new test fixtures.
"""

import pytest
from src.triggers.trigger_matcher import TriggerMatcher
from src.models.database import TriggerEmbedding


class DummyEmbedSvc:
    """Dummy embedding service for testing."""
    def __init__(self, dim=768):
        self.dim = dim

    async def generate_embedding(self, text: str):
        # simplistic deterministic embedding for tests
        t = (text or "").lower()
        if "remind" in t or "reminder" in t or "reminders" in t:
            return [1.0, 0.0, 0.0, 0.0]
        return [0.0, 1.0, 0.0, 0.0]

    async def batch_embed(self, texts):
        return [await self.generate_embedding(t) for t in texts]

    def embedding_to_bytes(self, emb):
        import numpy as np

        return np.array(emb, dtype="float32").tobytes()

    def bytes_to_embedding(self, data):
        import numpy as np

        return np.frombuffer(data, dtype="float32").tolist()

    def cosine_similarity(self, a, b):
        import numpy as np

        a = np.array(a, dtype=float)
        b = np.array(b, dtype=float)
        if np.linalg.norm(a) == 0 or np.linalg.norm(b) == 0:
            return 0.0
        return float((a / np.linalg.norm(a)) @ (b / np.linalg.norm(b)))


class TestTriggerEmbeddingsSeed:
    """Test suite for trigger embedding seeding."""

    @pytest.fixture(autouse=True)
    def seed_triggers_for_test(self, db_engine, monkeypatch):
        """Seed triggers before each test using the test database engine.
        
        This explicitly seeds triggers in the test class rather than
        relying solely on conftest.py's autouse fixture, ensuring the
        test has the correct trigger data available.
        """
        from sqlalchemy.orm import sessionmaker
        
        # Create a session maker bound to the test engine
        TestSessionLocal = sessionmaker(bind=db_engine, autoflush=False, autocommit=False, future=True)
        
        # Patch SessionLocal in trigger_matcher module so it uses the test DB
        # The module imports SessionLocal at load time, so we need to patch it there too
        monkeypatch.setattr("src.triggers.trigger_matcher.SessionLocal", TestSessionLocal)

    @pytest.mark.serial
    @pytest.mark.asyncio
    async def test_seed_triggers_and_match(self, db_session, monkeypatch):
        """Given: A monkeypatched embedding service
        When: Seeding triggers and matching a query
        Then: Should seed triggers and find matches."""
        # Point embedding service to dummy for seeding and matching
        monkeypatch.setattr("src.services.embedding_service.get_embedding_service", lambda: DummyEmbedSvc())

        # Import the async seeder after monkeypatching so it uses the dummy service
        from src.triggers.trigger_matcher import seed_triggers

        # Run seeding (will populate the test DB via conftest DATABASE_URL)
        await seed_triggers()

        # Ensure triggers exist in DB
        count = db_session.query(TriggerEmbedding).count()
        assert count > 0

        # Now test matcher finds a query_schedule trigger
        matcher = TriggerMatcher()
        matcher.embedding_service = DummyEmbedSvc()
        matcher._loaded_at = 0

        matches = await matcher.match_triggers("Do I have any reminders?", top_k=5)
        assert matches
        # At least one match should have action_type 'query_schedule'
        assert any(m.get("action_type") == "query_schedule" for m in matches)

