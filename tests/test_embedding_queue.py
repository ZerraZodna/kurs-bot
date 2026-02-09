import time
import pytest

from src.services.memory_manager import MemoryManager
from src.models.database import SessionLocal, Memory, init_db
import src.services.embedding_service as embedding_service
from src.config import settings


def setup_module(module):
    # Ensure DB tables exist for tests
    init_db()


def teardown_module(module):
    # no-op cleanup; tests remove created rows where appropriate
    pass


def test_inline_enqueue_persists_embedding():
    mm = MemoryManager()
    # create a memory without triggering embedding generation
    mem_id = mm.store_memory(user_id=9999, key="test_inline", value="inline value", generate_embedding=False)

    # Prepare a fake embedding list
    emb = [0.01] * settings.EMBEDDING_DIMENSION

    # Patch the enqueue helper to return the embedding inline
    orig_enqueue = embedding_service.enqueue_embedding_for_memory
    embedding_service._embed_queue = None
    embedding_service.enqueue_embedding_for_memory = lambda memory_id, text, delay=0: emb

    try:
        mm._schedule_embedding_generation(mem_id, "inline value")

        # small sleep to allow any synchronous work to finish
        time.sleep(0.1)

        session = SessionLocal()
        try:
            m = session.get(Memory, mem_id)
            assert m is not None
            assert m.embedding is not None, "Embedding bytes should be persisted for inline fallback"
            assert m.embedding_generated_at is not None
        finally:
            # cleanup
            if m:
                session.delete(m)
                session.commit()
            session.close()
    finally:
        embedding_service.enqueue_embedding_for_memory = orig_enqueue


def test_enqueue_returns_job_does_not_persist():
    mm = MemoryManager()
    mem_id = mm.store_memory(user_id=9998, key="test_enqueue", value="queued value", generate_embedding=False)

    class FakeJob:
        def __init__(self):
            self.id = "fake-job-1"

    orig_enqueue = embedding_service.enqueue_embedding_for_memory
    embedding_service._embed_queue = object()  # pretend queue exists
    embedding_service.enqueue_embedding_for_memory = lambda memory_id, text, delay=0: FakeJob()

    try:
        mm._schedule_embedding_generation(mem_id, "queued value")

        # give a moment
        time.sleep(0.05)

        session = SessionLocal()
        try:
            m = session.get(Memory, mem_id)
            assert m is not None
            # Since the job was enqueued, embedding should still be None
            assert m.embedding is None
        finally:
            if m:
                session.delete(m)
                session.commit()
            session.close()
    finally:
        embedding_service.enqueue_embedding_for_memory = orig_enqueue
