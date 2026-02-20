import os
import sys
import types
import importlib
import pytest

# NOTE: import-time prevention for the real Ollama client lives in
# `tests/conftest.py`. That conftest stub runs before test collection and
# prevents import-time model/HTTP initialization. `tests/helpers.py` should
# only contain per-test fixtures/monkeypatch helpers.


def _env_is_truthy(name: str) -> bool:
    """Return True for common truthy env values (1/true/yes/y)."""
    v = os.getenv(name)
    if not v:
        return False
    return str(v).strip().lower() in ("1", "true", "yes", "y")


def _get_embedding_dim() -> int:
    try:
        return int(os.getenv("EMBEDDING_DIMENSION", "384") or 384)
    except Exception:
        return 384


def _register_fake_faiss() -> None:
    """Install a lightweight pure-Python faiss stub into sys.modules.

    This avoids depending on native faiss in tests while preserving a
    minimal feature set used by the matcher/test utilities.
    """
    try:
        if not _env_is_truthy("TEST_USE_REAL_FAISS"):
            import numpy as _np

            if "faiss" not in sys.modules:
                fake_faiss = types.ModuleType("faiss")

                class _IndexFlatIP:
                    def __init__(self, dim):
                        self.d = dim
                        self._mat = _np.zeros((0, dim), dtype=_np.float32)
                        self._ids = _np.array([], dtype=_np.int64)

                    def add_with_ids(self, mat, ids):
                        try:
                            mat = _np.asarray(mat, dtype=_np.float32)
                            ids = _np.asarray(ids, dtype=_np.int64)
                            if self._mat.size == 0:
                                self._mat = mat.copy()
                                self._ids = ids.copy()
                            else:
                                self._mat = _np.vstack([self._mat, mat])
                                self._ids = _np.concatenate([self._ids, ids])
                        except Exception:
                            pass

                    def search(self, q, top_k):
                        q = _np.asarray(q, dtype=_np.float32)
                        if q.ndim == 1:
                            q = q.reshape(1, -1)
                        if self._mat.size == 0:
                            return _np.zeros((q.shape[0], 0)), _np.full((q.shape[0], 0), -1, dtype=_np.int64)
                        norms = _np.linalg.norm(self._mat, axis=1)
                        norms[norms == 0] = 1.0
                        mat_norm = self._mat / norms[:, None]
                        q_norm = q / (_np.linalg.norm(q, axis=1)[:, None] + 1e-12)
                        scores = mat_norm.dot(q_norm.T)
                        D = _np.zeros((q.shape[0], top_k), dtype=_np.float32)
                        I = _np.full((q.shape[0], top_k), -1, dtype=_np.int64)
                        for qi in range(q.shape[0]):
                            row = scores[:, qi]
                            order = _np.argsort(-row)[:top_k]
                            D[qi, : len(order)] = row[order]
                            I[qi, : len(order)] = self._ids[order]
                        return D, I

                class _IndexIDMap:
                    def __init__(self, index):
                        self._inner = index
                        try:
                            self.d = getattr(index, "d", None)
                        except Exception:
                            self.d = None

                    def add_with_ids(self, mat, ids):
                        return self._inner.add_with_ids(mat, ids)

                    def search(self, q, top_k):
                        return self._inner.search(q, top_k)

                fake_faiss.IndexFlatIP = _IndexFlatIP
                fake_faiss.IndexIDMap = _IndexIDMap
                sys.modules["faiss"] = fake_faiss
    except Exception:
        pass


def _make_fake_call_ollama():
    async def _fake_call_ollama(prompt: str, model: str | None = None, language: str | None = None) -> str:
        short = (prompt[:160] + "...") if prompt and len(prompt) > 160 else (prompt or "")
        return f"[MOCK_OLLAMA_REPLY] model={model or 'default'} lang={language or 'en'} text={short}"

    return _fake_call_ollama


def _patch_ollama_client(monkeypatch):
    fake = _make_fake_call_ollama()
    try:
        client_mod = importlib.import_module("src.services.dialogue.ollama_client")
    except Exception:
        client_mod = None

    if not _env_is_truthy("TEST_USE_REAL_OLLAMA"):
        if client_mod is not None:
            try:
                monkeypatch.setattr(client_mod, "call_ollama", fake)
            except Exception:
                pass


def _patch_ollama_online(monkeypatch):
    try:
        _online = importlib.import_module("src.services.ollama_online_test")
        try:
            monkeypatch.setattr(_online, "run_ollama_checks", lambda *a, **k: (True, []))
        except Exception:
            pass
    except Exception:
        pass


def _patch_embedding_service(monkeypatch):
    try:
        emb_mod = importlib.import_module("src.services.embedding_service")

        class _FakeEmbeddingService:
            def __init__(self, dim: int = _get_embedding_dim()):
                self.embedding_dimension = dim

            async def generate_embedding(self, text: str):
                if not text:
                    return None
                return [0.0] * self.embedding_dimension

            async def batch_embed(self, texts):
                out = []
                for t in texts:
                    out.append(None if not t else [0.0] * self.embedding_dimension)
                return out

            async def close(self):
                return None

        fake_emb = _FakeEmbeddingService()
        try:
            monkeypatch.setattr(emb_mod, "get_embedding_service", lambda: fake_emb)
            try:
                setattr(emb_mod, "_embedding_service", fake_emb)
            except Exception:
                pass
        except Exception:
            pass
    except Exception:
        pass


def _patch_httpx_client(monkeypatch):
    try:
        import httpx as _httpx
        import os as _os

        class _DummyResponse:
            def __init__(self, json_data=None, status_code=200):
                self._json = json_data if json_data is not None else {"embeddings": [[0.0] * _get_embedding_dim()]}
                self.status_code = status_code

            def raise_for_status(self):
                if self.status_code >= 400:
                    raise _httpx.HTTPStatusError("Mocked error", request=None, response=self)

            def json(self):
                return self._json

            @property
            def text(self):
                return ""

        class _DummyAsyncClient:
            async def __aenter__(self):
                return self

            async def __aexit__(self, exc_type, exc, tb):
                return False

            async def post(self, *args, **kwargs):
                # Fail fast on any attempt to call configured Ollama endpoints
                try:
                    url = args[0] if args else kwargs.get('url')
                except Exception:
                    url = None
                if url:
                    local = _os.getenv('LOCAL_OLLAMA_URL') or ''
                    cloud = _os.getenv('CLOUD_OLLAMA_URL') or ''
                    u = str(url)
                    if local and local in u:
                        raise RuntimeError(f"Blocked outbound call to LOCAL_OLLAMA_URL during tests: {u}")
                    if cloud and cloud in u:
                        raise RuntimeError(f"Blocked outbound call to CLOUD_OLLAMA_URL during tests: {u}")
                    # Also block common Ollama path fragments as a safety net
                    if 'ollama' in u and 'embed' in u or 'generate' in u:
                        raise RuntimeError(f"Blocked outbound Ollama-related HTTP call during tests: {u}")
                return _DummyResponse()

            async def get(self, *args, **kwargs):
                return _DummyResponse()

        try:
            monkeypatch.setattr(_httpx, "AsyncClient", _DummyAsyncClient)
        except Exception:
            pass
    except Exception:
        pass


@pytest.fixture(autouse=True)
def install_test_mocks(monkeypatch):
    """Consolidated test helpers: fake Ollama, embedding service, httpx client, and faiss stub.

    This centralizes test-only patches so individual test files stay small.
    """

    # Register lightweight stubs/mocks used by tests
    _register_fake_faiss()
    _patch_ollama_client(monkeypatch)
    _patch_ollama_online(monkeypatch)
    _patch_embedding_service(monkeypatch)
    _patch_httpx_client(monkeypatch)

    yield
