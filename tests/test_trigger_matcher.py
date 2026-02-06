import asyncio
import pytest
from src.services.trigger_matcher import TriggerMatcher
from src.models.database import SessionLocal, TriggerEmbedding


class DummyEmbedSvc:
    def __init__(self, dim=4):
        self.dim = dim

    async def generate_embedding(self, text: str):
        # deterministic mapping based on text
        if "alpha" in text:
            return [1.0, 0.0, 0.0, 0.0]
        return [0.0, 1.0, 0.0, 0.0]

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
    # insert two triggers
    t1 = TriggerEmbedding(name="alpha_trigger", action_type="next_lesson", embedding=svc.embedding_to_bytes([1,0,0,0]), threshold=0.5)
    t2 = TriggerEmbedding(name="beta_trigger", action_type="enter_rag", embedding=svc.embedding_to_bytes([0,1,0,0]), threshold=0.5)
    db.add(t1); db.add(t2); db.commit()

    matcher = TriggerMatcher()
    # replace embedding service
    matcher.embedding_service = svc
    # force reload
    matcher._loaded_at = 0
    matches = await matcher.match_triggers("Please alpha please", top_k=2)
    assert matches
    assert matches[0]["name"] == "alpha_trigger"
    assert matches[0]["score"] > matches[1]["score"]
