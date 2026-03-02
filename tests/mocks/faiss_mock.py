"""FAISS mocking utilities."""

import sys
import types
import importlib.machinery
from typing import Optional, List
import numpy as np


class FakeIndexFlatIP:
    """Fake FAISS IndexFlatIP for testing."""
    
    def __init__(self, dim: int):
        self.d = dim
        self._mat = np.zeros((0, dim), dtype=np.float32)
        self._ids = np.array([], dtype=np.int64)
    
    def add_with_ids(self, mat, ids):
        """Add vectors with IDs."""
        mat = np.asarray(mat, dtype=np.float32)
        ids = np.asarray(ids, dtype=np.int64)
        
        if self._mat.size == 0:
            self._mat = mat.copy()
            self._ids = ids.copy()
        else:
            self._mat = np.vstack([self._mat, mat])
            self._ids = np.concatenate([self._ids, ids])
    
    def search(self, q, top_k: int):
        """Search for nearest neighbors."""
        q = np.asarray(q, dtype=np.float32)
        if q.ndim == 1:
            q = q.reshape(1, -1)
        
        if self._mat.size == 0:
            return (
                np.zeros((q.shape[0], 0), dtype=np.float32),
                np.full((q.shape[0], 0), -1, dtype=np.int64)
            )
        
        # Normalize vectors
        norms = np.linalg.norm(self._mat, axis=1)
        norms[norms == 0] = 1.0
        mat_norm = self._mat / norms[:, None]
        
        q_norm = q / (np.linalg.norm(q, axis=1)[:, None] + 1e-12)
        
        # Compute cosine similarity
        scores = mat_norm.dot(q_norm.T)
        
        # Get top-k results
        D = np.zeros((q.shape[0], top_k), dtype=np.float32)
        I = np.full((q.shape[0], top_k), -1, dtype=np.int64)
        
        for qi in range(q.shape[0]):
            row = scores[:, qi]
            order = np.argsort(-row)[:top_k]
            D[qi, :len(order)] = row[order]
            I[qi, :len(order)] = self._ids[order]
        
        return D, I


class FakeIndexIDMap:
    """Fake FAISS IndexIDMap for testing."""
    
    def __init__(self, index):
        self._inner = index
        try:
            self.d = getattr(index, "d", None)
        except Exception:
            self.d = None
    
    def add_with_ids(self, mat, ids):
        return self._inner.add_with_ids(mat, ids)
    
    def search(self, q, top_k: int):
        return self._inner.search(q, top_k)


def create_fake_faiss_module() -> types.ModuleType:
    """Create a fake faiss module."""
    fake_faiss = types.ModuleType("faiss")
    fake_faiss.__spec__ = importlib.machinery.ModuleSpec(
        "faiss",
        None,
        is_package=False
    )
    
    fake_faiss.IndexFlatIP = FakeIndexFlatIP
    fake_faiss.IndexIDMap = FakeIndexIDMap
    
    return fake_faiss


def register_fake_faiss() -> None:
    """Register fake faiss module in sys.modules.
    
    Call this at import time to prevent real faiss initialization.
    """
    if "faiss" not in sys.modules:
        sys.modules["faiss"] = create_fake_faiss_module()


def patch_faiss(monkeypatch) -> None:
    """Patch faiss module.
    
    Usage:
        from tests.mocks.faiss_mock import patch_faiss
        
        def test_something(monkeypatch):
            patch_faiss(monkeypatch)
            # ... test code
    """
    import faiss as faiss_module
    
    monkeypatch.setattr(faiss_module, "IndexFlatIP", FakeIndexFlatIP)
    monkeypatch.setattr(faiss_module, "IndexIDMap", FakeIndexIDMap)
