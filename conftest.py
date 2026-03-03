"""
Pytest configuration for kurs-bot tests.
Central location for all test database setup and configuration.
"""

# Load .env early so its variables are available to pytest and any imported
# project modules during collection. We implement a small, dependency-free
# loader so tests do not need `python-dotenv` installed.
import os
os.environ.setdefault("IS_TEST_ENV", "1")
from pathlib import Path

def _load_dotenv_if_present():
    repo_root = Path(__file__).resolve().parent
    env_path = repo_root / '.env'
    if not env_path.exists():
        return
    try:
        with env_path.open('r', encoding='utf8') as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith('#'):
                    continue
                if '=' not in line:
                    continue
                k, v = line.split('=', 1)
                k = k.strip()
                v = v.strip().strip('"')
                # Do not overwrite environment variables explicitly set
                if k and os.getenv(k) is None:
                    os.environ[k] = v
    except Exception:
        # Best-effort: do not fail pytest startup if .env can't be read
        pass


_load_dotenv_if_present()
import sys
import types
from typing import Optional
# Insert an import-time stub for the Ollama client so early imports during
# pytest collection cannot trigger real Ollama/model initialization when
# TEST_USE_REAL_OLLAMA is not set truthy. This prevents import-order races
# where other modules bind `call_ollama` before test fixtures run.
_test_use_real = os.getenv("TEST_USE_REAL_OLLAMA")
if not _test_use_real or str(_test_use_real).strip().lower() not in ("1", "true", "yes", "y"):
    mod_name = "src.services.dialogue.ollama_client"
    if mod_name not in sys.modules:
        _fake = types.ModuleType(mod_name)

        async def _fake_call_ollama(prompt: str, model: Optional[str] = None, language: Optional[str] = None) -> str:
            short = (prompt[:160] + "...") if prompt and len(prompt) > 160 else (prompt or "")
            return f"[MOCK_OLLAMA_REPLY] model={model or 'default'} lang={language or 'en'} text={short}"

        async def _fake_stream_ollama(prompt: str, model: Optional[str] = None, language: Optional[str] = None, temperature=None):
            short = (prompt[:160] + "...") if prompt and len(prompt) > 160 else (prompt or "")
            yield f"[MOCK_OLLAMA_STREAM] model={model or 'default'} lang={language or 'en'} text={short}"

        setattr(_fake, "call_ollama", _fake_call_ollama)
        setattr(_fake, "stream_ollama", _fake_stream_ollama)
        sys.modules[mod_name] = _fake
        # Ensure the package exposes attributes that tests may monkeypatch
        try:
            import importlib

            pkg = importlib.import_module("src.services.dialogue")
            try:
                setattr(pkg, "ollama_client", _fake)
                setattr(pkg, "call_ollama", _fake.call_ollama)
            except Exception:
                pass
        except Exception:
            # If the package cannot be imported now, leave the fake submodule
            # in sys.modules so a later import will resolve to it.
            pass

import time
import time
from pathlib import Path
import pytest
# Ensure test DB is used for the test session
# (override early so modules importing settings pick up test DB URL)

# Test database configuration (single source of truth)
TEST_DB_PATH = Path('src/data/test.db')
TEST_DB_URL = f'sqlite:///{TEST_DB_PATH}'

# Safety check: warn if DATABASE_URL points to prod.db before we override it
# This ensures the warning appears at test startup, not after tests run
_original_db_url = os.environ.get('DATABASE_URL', '')
if 'prod.db' in _original_db_url:
    # Use stderr and flush to ensure immediate output (not buffered by pytest -q)
    import sys
    sys.stderr.write("\n⚠️  WARNING: Detected test run with DATABASE_URL pointing to prod.db - overriding to test.db to avoid data loss.\n")
    sys.stderr.flush()
    import logging
    logging.getLogger(__name__).warning(
        "Detected test run with DATABASE_URL pointing to prod.db - overriding to test.db to avoid data loss."
    )

# Export DATABASE_URL so code using settings picks up the test DB
os.environ['DATABASE_URL'] = TEST_DB_URL


@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """
    Setup test environment and cleanup after tests.
    - Removes old test database before tests start
    - Removes test database after tests complete (with retry for Windows file locking)
    """
    # Remove old test database if it exists
    if TEST_DB_PATH.exists():
        try:
            TEST_DB_PATH.unlink()
            print("\n🧪 Cleaned up old test database")
        except PermissionError:
            print("\n⚠️  Old test database locked, will be overwritten")
    
    print(f"🧪 Using test database: {TEST_DB_URL}")
    # Ensure schema exists in test DB
    try:
        # Prevent background threads (lifespan) from starting during tests
        os.environ.setdefault("IS_TEST_ENV", "1")
        # Always mock FAISS in tests - the codebase uses numpy-based similarity
        # instead of native FAISS, so we provide a lightweight Python stub.
        try:
            import sys, types, numpy as _np

            if "faiss" not in sys.modules:
                import importlib.machinery
                fake_faiss = types.ModuleType("faiss")
                fake_faiss.__spec__ = importlib.machinery.ModuleSpec("faiss", None, is_package=False)

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
        from src.models.database import init_db

        init_db()
    except Exception as e:
        print(f"⚠️  Could not initialize test DB schema: {e}")
    
    yield
    
    # Cleanup after all tests (with retry for Windows file locking)
    if TEST_DB_PATH.exists():
        for attempt in range(3):
            try:
                TEST_DB_PATH.unlink()
                print("\n✅ Test session complete - cleaned up test database")
                break
            except PermissionError:
                if attempt < 2:
                    time.sleep(0.5)  # Wait briefly for file locks to release
                else:
                    print("\n⚠️  Test session complete - test.db is locked (will be cleaned on next run)")
    else:
        print("\n✅ Test session complete")


def pytest_collection_modifyitems(config, items):
    """Skip manual tests that are intended to be run interactively.

    The file `tests/test_embeddings_manual.py` is a manual/interactive script
    that defines an async test function without pytest decorators. Skip it
    during automated test runs.
    """
    for item in list(items):
        try:
            name = item.fspath.basename
        except Exception:
            continue
        if name == "test_embeddings_manual.py":
            import pytest as _pytest
            item.add_marker(_pytest.mark.skip(reason="Manual test - skipped in CI"))


def pytest_configure(config):
    """Allow overriding Ollama model settings for tests via environment variables.

    Usage (example):
      TEST_OLLAMA_MODEL="qwen3:test" \
        TEST_OLLAMA_CHAT_RAG_MODEL="llama3.2:test" \
        TEST_NON_ENGLISH_OLLAMA_MODEL="gpt-oss:test" \
        pytest tests/...

    This function copies any `TEST_*` overrides into the corresponding
    runtime env var and reloads `src.config` so `settings` picks them up.
    """
    # Default all test models to `llama3.2:3b` unless a TEST_* override is provided.
    defaults_model = "llama3.2:3b"

    def choose_model(test_env_name: str) -> str:
        # Respect explicit TEST_* overrides except for placeholder names
        # often used in examples (e.g. 'llama3.2:test'). Treat those as
        # not provided and fall back to the canonical test model.
        val = os.getenv(test_env_name)
        if not val:
            return defaults_model
        # Ignore placeholder model names that end with ':test'
        if val.strip().endswith(":test"):
            return defaults_model
        return val

    overrides = {
        "OLLAMA_MODEL": choose_model("TEST_OLLAMA_MODEL"),
        "OLLAMA_CHAT_RAG_MODEL": choose_model("TEST_OLLAMA_CHAT_RAG_MODEL"),
        "NON_ENGLISH_OLLAMA_MODEL": choose_model("TEST_NON_ENGLISH_OLLAMA_MODEL"),
    }
    changed = False
    for k, v in overrides.items():
        if v:
            os.environ[k] = v
            changed = True
    # Always apply the test defaults (or user-provided TEST_*) to ensure tests
    # run with a consistent model selection.
    if changed:
        try:
            import importlib
            import src.config as cfg
            importlib.reload(cfg)
            applied = [k for k, v in overrides.items() if v]
            print(f"🔧 Test overrides applied: {', '.join(applied)}")
        except Exception as e:
            print(f"⚠️ Could not reload src.config after env override: {e}")
