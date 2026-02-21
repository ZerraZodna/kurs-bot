import logging
from typing import List, Optional, Tuple

import numpy as np

from src.config import settings

logger = logging.getLogger(__name__)


class VectorIndex:
    """Simple vector index with optional Faiss backend and numpy fallback.

    Usage:
      vi = VectorIndex()
      vi.build(ids, embeddings)
      results = vi.search(query, top_k=5)  # returns list of (id, score)
    """

    def __init__(self, use_faiss: Optional[bool] = None):
        self._ids: List[int] = []
        self._matrix: Optional[np.ndarray] = None
        self._faiss_index = None
        self._use_faiss = False
        if use_faiss is None:
            use_faiss = settings.USE_REAL_FAISS
        if use_faiss:
            try:
                import faiss  # type: ignore

                self._faiss = faiss
                self._use_faiss = True
            except Exception:
                logger.debug("Faiss not available, falling back to numpy search")
                self._faiss = None

    def _normalize_rows(self, mat: np.ndarray) -> np.ndarray:
        norms = np.linalg.norm(mat, axis=1, keepdims=True)
        norms[norms == 0] = 1.0
        return mat / norms

    def build(self, ids: List[int], embeddings: List[List[float]]):
        if not ids or not embeddings:
            self._ids = []
            self._matrix = None
            self._faiss_index = None
            return

        # Convert to 2D numpy array of float32 and pad to consistent width
        max_dim = max(len(e) for e in embeddings)
        mat = np.zeros((len(embeddings), max_dim), dtype=np.float32)
        for i, e in enumerate(embeddings):
            arr = np.array(e, dtype=np.float32)
            mat[i, : arr.size] = arr

        # Normalize rows for cosine-similarity via inner product
        mat_norm = self._normalize_rows(mat)

        self._ids = list(ids)

        if self._use_faiss and self._faiss is not None:
            try:
                dim = mat_norm.shape[1]
                # IndexFlatIP uses inner-product which equals cosine on normalized vectors
                index = self._faiss.IndexFlatIP(dim)
                # Use IDMap so searches return original ids
                index = self._faiss.IndexIDMap(index)
                index.add_with_ids(mat_norm.astype(np.float32), np.array(self._ids, dtype=np.int64))
                self._faiss_index = index
                self._matrix = None
                logger.info("Built Faiss index with %d vectors (dim=%d)", mat_norm.shape[0], dim)
                return
            except Exception as e:
                logger.warning("Failed to build Faiss index, falling back to numpy: %s", e)

        # Fallback: keep numpy matrix
        self._matrix = mat_norm
        self._faiss_index = None
        logger.info("Built numpy fallback index with %d vectors (dim=%d)", mat_norm.shape[0], mat_norm.shape[1])

    def search(self, query: List[float], top_k: int = 5) -> List[Tuple[int, float]]:
        """Search for nearest neighbours by cosine similarity.

        Returns list of (id, score) sorted by descending score.
        """
        if not query:
            return []

        if self._faiss_index is not None:
            try:
                q = np.array(query, dtype=np.float32)
                # Pad or trim to match index dim
                dim = self._faiss_index.d
                if q.size != dim:
                    qp = np.zeros(dim, dtype=np.float32)
                    qp[: q.size] = q[:dim]
                    q = qp
                # normalize
                q_norm = q / (np.linalg.norm(q) or 1.0)
                D, I = self._faiss_index.search(q_norm.reshape(1, -1).astype(np.float32), top_k)
                results = []
                for score, idx in zip(D[0], I[0]):
                    if idx == -1:
                        continue
                    results.append((int(idx), float(score)))
                return results
            except Exception as e:
                logger.warning("Faiss search failed, falling back to numpy: %s", e)

        if self._matrix is None or not len(self._ids):
            return []

        q = np.array(query, dtype=np.float32)
        if q.size != self._matrix.shape[1]:
            qp = np.zeros(self._matrix.shape[1], dtype=np.float32)
            qp[: q.size] = q[: self._matrix.shape[1]]
            q = qp
        q = q / (np.linalg.norm(q) or 1.0)

        # Compute dot products with all rows (matrix @ q) -> scores
        scores = self._matrix.dot(q)
        if top_k >= scores.size:
            order = np.argsort(-scores)
        else:
            order = np.argpartition(-scores, top_k - 1)[:top_k]
            order = order[np.argsort(-scores[order])]

        results = []
        for idx in order:
            results.append((int(self._ids[idx]), float(scores[idx])))
        return results


__all__ = ["VectorIndex"]
