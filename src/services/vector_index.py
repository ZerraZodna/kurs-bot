"""
Vector Index adapter

Provides a minimal adapter with pluggable backends. Current backends:
- local: in-process brute-force index (good for dev / testing)
- redis: stores vectors in Redis and performs client-side similarity scan (safe fallback)

Replace or extend with FAISS / Redis Vector for production.
"""
from __future__ import annotations

import os
import threading
import pickle
import numpy as np
from typing import Iterable, List, Tuple

try:
    from redis import Redis
except Exception:
    Redis = None  # type: ignore


class VectorIndexClient:
    def __init__(self, backend: str = "local"):
        self.backend = backend
        if backend == "local":
            # In-memory dict of id -> np.ndarray
            self._vectors = {}
            self._lock = threading.Lock()
        elif backend == "redis":
            if Redis is None:
                raise RuntimeError("redis package not available")
            url = os.getenv("REDIS_URL", "redis://localhost:6379")
            self._redis = Redis.from_url(url)
            self._prefix = os.getenv("VECTOR_REDIS_PREFIX", "vector:")
        else:
            raise ValueError(f"Unsupported vector index backend: {backend}")

    @classmethod
    def from_env(cls) -> "VectorIndexClient":
        backend = os.getenv("VECTOR_INDEX_BACKEND", "local")
        return cls(backend=backend)

    def upsert(self, id: str, vector: List[float]):
        arr = np.array(vector, dtype=np.float32)
        if self.backend == "local":
            with self._lock:
                self._vectors[id] = arr
            return True

        # redis backend: store as pickled bytes (simple portable format)
        key = self._prefix + id
        data = pickle.dumps(arr, protocol=pickle.HIGHEST_PROTOCOL)
        self._redis.set(key, data)
        return True

    def bulk_upsert(self, items: Iterable[Tuple[str, List[float]]]):
        if self.backend == "local":
            with self._lock:
                for id, vector in items:
                    self._vectors[id] = np.array(vector, dtype=np.float32)
            return True

        pipe = self._redis.pipeline()
        for id, vector in items:
            key = self._prefix + id
            data = pickle.dumps(np.array(vector, dtype=np.float32), protocol=pickle.HIGHEST_PROTOCOL)
            pipe.set(key, data)
        pipe.execute()
        return True

    def query(self, vector: List[float], k: int = 5) -> List[Tuple[str, float]]:
        """
        Brute-force k-NN query returning list of (id, similarity)
        Similarity is cosine similarity in range [-1,1].
        """
        q = np.array(vector, dtype=np.float32)
        q_norm = np.linalg.norm(q)
        if q_norm == 0:
            return []
        q = q / q_norm

        results: List[Tuple[str, float]] = []
        if self.backend == "local":
            with self._lock:
                for id, vec in self._vectors.items():
                    if vec is None:
                        continue
                    v_norm = np.linalg.norm(vec)
                    if v_norm == 0:
                        continue
                    sim = float(np.dot(q, vec / v_norm))
                    results.append((id, sim))

        else:
            # redis backend: fetch keys and scan client-side
            keys = list(self._redis.scan_iter(match=self._prefix + "*"))
            if not keys:
                return []
            pipe = self._redis.pipeline()
            for kkey in keys:
                pipe.get(kkey)
            blobs = pipe.execute()
            for raw in blobs:
                if not raw:
                    continue
                try:
                    vec = pickle.loads(raw)
                except Exception:
                    continue
                v_norm = np.linalg.norm(vec)
                if v_norm == 0:
                    continue
                sim = float(np.dot(q, vec / v_norm))
                # extract id from key by stripping prefix
                # we have keys list same order as blobs
                results.append((kkey.decode().replace(self._prefix, ""), sim))

        # sort and return top-k
        results.sort(key=lambda x: x[1], reverse=True)
        return results[:k]

    def persist_to_file(self, path: str):
        if self.backend != "local":
            raise RuntimeError("persist_to_file only supported for local backend")
        with open(path, "wb") as f:
            pickle.dump(self._vectors, f)

    def load_from_file(self, path: str):
        if self.backend != "local":
            raise RuntimeError("load_from_file only supported for local backend")
        with open(path, "rb") as f:
            self._vectors = pickle.load(f)
