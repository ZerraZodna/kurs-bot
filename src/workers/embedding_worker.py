import asyncio
import logging
import datetime
import time

# Optional imports: avoid failing test collection when redis/rq aren't installed.
try:
    from redis import Redis
except Exception:
    Redis = None

try:
    from rq import Retry
except Exception:
    Retry = None

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

        # Optional: push to vector index if configured via feature flag
        if settings.VECTOR_INDEX_ENABLED:
            try:
                from src.services.vector_index import VectorIndexClient

                idx = VectorIndexClient.from_env()
                # Best-effort upsert with small retry/backoff and latency logging
                attempts = 2
                for attempt in range(attempts + 1):
                    t0 = time.time()
                    try:
                        idx.upsert(str(memory_id), emb)
                        latency = time.time() - t0
                        logger.info("Upserted vector index for memory %s latency=%.3fs attempt=%d", memory_id, latency, attempt)
                        break
                    except Exception as e:
                        latency = time.time() - t0
                        logger.exception("Upsert attempt %d failed for memory %s (%.3fs): %s", attempt, memory_id, latency, e)
                        if attempt < attempts:
                            time.sleep(0.25 * (attempt + 1))
            except Exception as e:
                logger.exception("Failed to upsert vector index for memory %s: %s", memory_id, e)

    finally:
        session.close()


def generate_and_store_embeddings_batch(memory_items: list, force: bool = False):
    """RQ worker task: process a batch of (memory_id, text) items.

    This function is synchronous so it can be enqueued by RQ. It will call
    the async `batch_embed` API via `asyncio.run` and persist results.
    """
    svc = get_embedding_service()
    texts = [text for (_id, text) in memory_items]
    start = datetime.datetime.utcnow()
    emb_list = asyncio.run(svc.batch_embed(texts))

    session = SessionLocal()
    try:
        upsert_items = []
        for (mem_id, _text), emb in zip(memory_items, emb_list):
            if emb is None:
                logger.error("Embedding generation failed for memory_id=%s (batch)", mem_id)
                # Raise to allow RQ to mark/handle failure per job
                raise RuntimeError(f"Embedding generation failed for memory {mem_id}")

            emb_bytes = EmbeddingService.embedding_to_bytes(emb)

            try:
                mem = session.get(Memory, mem_id)
                if mem is None:
                    logger.error("Memory not found: %s", mem_id)
                    continue

                # Skip if embedding exists and versions match (unless force)
                if mem.embedding is not None and not force:
                    if mem.embedding_version == settings.EMBEDDING_VERSION:
                        logger.info("Skipping embedding for memory %s; up-to-date (batch)", mem_id)
                        continue

                mem.embedding = emb_bytes
                mem.embedding_version = settings.EMBEDDING_VERSION
                mem.embedding_generated_at = datetime.datetime.utcnow()
                session.add(mem)
                session.commit()
                logger.info("Stored embedding for memory %s (batch)", mem_id)

                # Optional: collect items for vector index bulk upsert if configured
                if settings.VECTOR_INDEX_ENABLED:
                    upsert_items.append((str(mem_id), emb))

            except Exception:
                session.rollback()
                raise

        # Perform bulk upsert if configured
        if settings.VECTOR_INDEX_ENABLED and upsert_items:
            try:
                from src.services.vector_index import VectorIndexClient

                idx = VectorIndexClient.from_env()
                attempts = 2
                for attempt in range(attempts + 1):
                    t0 = time.time()
                    try:
                        idx.bulk_upsert(upsert_items)
                        latency = time.time() - t0
                        logger.info("Bulk upserted %d vectors latency=%.3fs attempt=%d", len(upsert_items), latency, attempt)
                        break
                    except Exception as e:
                        latency = time.time() - t0
                        logger.exception("Bulk upsert attempt %d failed (%.3fs): %s", attempt, latency, e)
                        if attempt < attempts:
                            time.sleep(0.25 * (attempt + 1))
            except Exception as e:
                logger.exception("Failed bulk upsert of vectors: %s", e)

        elapsed = (datetime.datetime.utcnow() - start).total_seconds()
        logger.info("Processed embedding batch size=%d elapsed=%.2fs", len(memory_items), elapsed)

    finally:
        session.close()
