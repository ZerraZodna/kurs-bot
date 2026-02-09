import asyncio
import logging
import os
import datetime

from redis import Redis
from rq import Retry

from src.models.database import SessionLocal, Memory
from src.services.embedding_service import get_embedding_service, EmbeddingService
from src.config import settings

logger = logging.getLogger(__name__)


def generate_and_store_embedding(memory_id: int, text: str, force: bool = False):
    """RQ worker task: generate embedding for a memory and persist it.

    This function is intentionally synchronous so it can be enqueued by RQ.
    It uses `asyncio.run` to call into the async embedding service.
    """
    svc = get_embedding_service()
    emb = asyncio.run(svc.generate_embedding(text))
    if emb is None:
        logger.error("Embedding generation failed for memory_id=%s", memory_id)
        # Let RQ retry according to job settings
        raise RuntimeError("Embedding generation failed")

    emb_bytes = EmbeddingService.embedding_to_bytes(emb)

    session = SessionLocal()
    try:
        mem = session.get(Memory, memory_id)
        if mem is None:
            logger.error("Memory not found: %s", memory_id)
            return

        # Skip if embedding exists and versions match (unless force)
        if mem.embedding is not None and not force:
            if mem.embedding_version == settings.EMBEDDING_VERSION:
                logger.info("Skipping embedding for memory %s; up-to-date", memory_id)
                return

        mem.embedding = emb_bytes
        mem.embedding_version = settings.EMBEDDING_VERSION
        mem.embedding_generated_at = datetime.datetime.utcnow()
        session.add(mem)
        session.commit()
        logger.info("Stored embedding for memory %s", memory_id)

        # Optional: push to vector index if configured via env variable
        if os.getenv("VECTOR_INDEX_ENABLED", "false").lower() == "true":
            try:
                from src.services.vector_index import VectorIndexClient

                idx = VectorIndexClient.from_env()
                idx.upsert(str(memory_id), emb)
                logger.info("Upserted vector index for memory %s", memory_id)
            except Exception as e:
                logger.exception("Failed to upsert vector index for memory %s: %s", memory_id, e)

    finally:
        session.close()
