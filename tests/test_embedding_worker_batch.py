import pytest
import datetime

from src.models.database import SessionLocal, Memory, init_db
from src.workers.embedding_worker import generate_and_store_embeddings_batch
from src.services.embedding_service import EmbeddingService


def setup_module(module):
    init_db()


def teardown_module(module):
    # Nothing to tear down globally; tests clean up their rows
    pass


def test_generate_and_store_embeddings_batch_inline():
    session = SessionLocal()
    try:
        # Create two memories to embed
        m1 = Memory(user_id=12345, category='fact', key='btest1', value='hello world', is_active=True)
        m2 = Memory(user_id=12345, category='fact', key='btest2', value='another one', is_active=True)
        session.add(m1)
        session.add(m2)
        session.commit()

        # Prepare items (memory_id, text)
        items = [(m1.memory_id, m1.value), (m2.memory_id, m2.value)]

        # Monkeypatch a deterministic embedding generator by replacing
        # EmbeddingService.generate_embedding with a simple function via instance
        svc = EmbeddingService()

        async def fake_generate(text: str):
            # return a small fixed-dimension embedding matching settings
            return [0.01] * svc.embedding_dimension

        svc.generate_embedding = fake_generate  # type: ignore
        async def fake_batch(texts):
            return await __import__('asyncio').gather(*[fake_generate(t) for t in texts])

        svc.batch_embed = fake_batch  # type: ignore

        # Patch get_embedding_service to return our instance
        import src.services.embedding_service as emb_mod
        orig_get = emb_mod.get_embedding_service
        emb_mod._embedding_service = svc

        try:
            # Call the batch worker directly (inline execution)
            generate_and_store_embeddings_batch(items)

            # Verify embeddings were stored (expire to refresh from DB)
            session.expire_all()
            updated_m1 = session.get(Memory, m1.memory_id)
            updated_m2 = session.get(Memory, m2.memory_id)
            assert updated_m1.embedding is not None
            assert updated_m2.embedding is not None
        finally:
            emb_mod._embedding_service = None

    finally:
        # cleanup
        try:
            session.delete(session.get(Memory, m1.memory_id))
            session.delete(session.get(Memory, m2.memory_id))
            session.commit()
        except Exception:
            session.rollback()
        session.close()
