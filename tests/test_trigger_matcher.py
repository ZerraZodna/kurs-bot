import asyncio
import pytest
from src.triggers.trigger_matcher import TriggerMatcher
from src.models.database import SessionLocal, TriggerEmbedding


class DummyEmbedSvc:
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


@pytest.fixture()
def db():
    db = SessionLocal()
    yield db
    db.close()


@pytest.mark.asyncio
async def test_matcher_prefers_closest(db):
    svc = DummyEmbedSvc()
    # clear existing triggers to make the test deterministic, then insert two seed-like triggers
    db.query(TriggerEmbedding).delete()
    db.commit()

    t1 = TriggerEmbedding(name="create_schedule", action_type="create_schedule", embedding=svc.embedding_to_bytes([1,0,0,0]), threshold=0.5)
    t2 = TriggerEmbedding(name="enter_rag", action_type="enter_rag", embedding=svc.embedding_to_bytes([0,1,0,0]), threshold=0.5)
    db.add(t1); db.add(t2); db.commit()

    matcher = TriggerMatcher()
    # replace embedding service
    matcher.embedding_service = svc
    # force reload
    matcher._loaded_at = 0
    matches = await matcher.match_triggers("Please remind me every day", top_k=2)
    assert matches
    assert matches[0]["name"] == "create_schedule"
    assert matches[0]["score"] > matches[1]["score"]
