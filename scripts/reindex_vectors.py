"""
Reindex existing memory embeddings into the vector index.

Usage:
    python scripts/reindex_vectors.py --batch 100

By default will upsert all `memories` rows that have a non-null `embedding` and
whose `embedding_version` matches `EMBEDDING_VERSION` in settings. If a memory
is missing an embedding, the script can optionally enqueue an embedding job.
"""
import argparse
import logging
import sys
import os

# Ensure project root is on sys.path so `import src.*` works when invoked
# as a script (e.g. `python scripts/reindex_vectors.py`).
ROOT = os.path.abspath(os.path.join(os.path.dirname(__file__), ".."))
if ROOT not in sys.path:
    sys.path.insert(0, ROOT)

from src.models.database import SessionLocal, Memory
from src.services.vector_index import VectorIndexClient
from src.services.embedding_service import get_embedding_service, enqueue_embedding_for_memory
from src.config import settings

logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)


def main(batch: int = 100, enqueue_missing: bool = False):
    idx = VectorIndexClient.from_env()
    session = SessionLocal()
    try:
        query = session.query(Memory).filter(Memory.embedding.isnot(None))
        total = query.count()
        logger.info("Found %s memories with embeddings", total)
        offset = 0
        while True:
            rows = query.offset(offset).limit(batch).all()
            if not rows:
                break
            items = []
            for mem in rows:
                try:
                    emb = mem.embedding
                    # Convert bytes to list[float]
                    from src.services.embedding_service import EmbeddingService
                    vec = EmbeddingService.bytes_to_embedding(emb)
                    if vec is None:
                        logger.warning("Failed to deserialize embedding for memory %s", mem.memory_id)
                        continue
                    items.append((str(mem.memory_id), vec))
                except Exception as e:
                    logger.exception("Error preparing mem %s: %s", mem.memory_id, e)
            if items:
                idx.bulk_upsert(items)
                logger.info("Upserted %s vectors to index", len(items))
            offset += batch

        if enqueue_missing:
            # Enqueue memories missing embeddings
            missing_query = session.query(Memory).filter(Memory.embedding.is_(None))
            count_missing = missing_query.count()
            logger.info("Found %s memories missing embeddings", count_missing)
            for mem in missing_query:
                enqueue_embedding_for_memory(mem.memory_id, mem.value)
                logger.info("Enqueued embedding job for memory %s", mem.memory_id)

    finally:
        session.close()


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--batch", type=int, default=100)
    parser.add_argument("--enqueue-missing", action="store_true", help="Enqueue jobs for missing embeddings")
    args = parser.parse_args()
    main(batch=args.batch, enqueue_missing=args.enqueue_missing)
