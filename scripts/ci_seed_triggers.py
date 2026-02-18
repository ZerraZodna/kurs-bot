"""Seed deterministic trigger embeddings for CI.

This script generates stable, dependency-free embeddings for the canonical
starter triggers and inserts them into the `trigger_embeddings` table.

It is intended to run in CI before tests so the trigger matcher has data
without requiring heavy ML dependencies or an Ollama server.
"""

from __future__ import annotations

import sys
from pathlib import Path

# Ensure the repository root is on sys.path so `import src...` works when
# running this script directly (e.g., in CI or locally as `python scripts/...`).
REPO_ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(REPO_ROOT))

import hashlib
import numpy as np
from src.triggers.trigger_matcher import STARTER
from src.models.database import TriggerEmbedding, SessionLocal, init_db
from src.config import settings


def hash_embedding(text: str, dim: int):
    """Create a deterministic float32 embedding for `text` of length `dim`.

    Uses repeated SHA256 to produce enough bytes, maps uint32 -> [-1, 1), and
    normalizes to unit length so cosine similarities behave sensibly.
    """
    b = b""
    i = 0
    # accumulate enough bytes
    while len(b) < dim * 4:
        b += hashlib.sha256(f"{text}:{i}".encode("utf-8")).digest()
        i += 1

    arr = np.empty(dim, dtype=np.float32)
    for j in range(dim):
        chunk = b[j * 4 : (j + 1) * 4]
        val = int.from_bytes(chunk, "big")
        # map uint32 -> [-1, 1)
        f = (val / 2 ** 32) * 2.0 - 1.0
        arr[j] = np.float32(f)

    norm = np.linalg.norm(arr)
    if norm == 0:
        return arr
    return (arr / norm).astype(np.float32)


def main():
    dim = getattr(settings, "EMBEDDING_DIMENSION", 384) or 384
    # Ensure database tables exist before inserting (CI DB is ephemeral)
    init_db()
    db = SessionLocal()
    try:
        # Clear existing starter entries with same names to avoid duplicates
        # (safe in CI ephemeral DBs)
        for spec in STARTER:
            utterance = spec["utterance"]
            emb = hash_embedding(utterance, dim)
            b = emb.tobytes()
            te = TriggerEmbedding(
                name=spec.get("name") or utterance,
                action_type=spec["action_type"],
                embedding=b,
                threshold=spec.get("threshold", 0.75),
            )
            db.add(te)
        db.commit()
        print("Seeded trigger_embeddings (deterministic hashes).")
    finally:
        db.close()


if __name__ == "__main__":
    main()
