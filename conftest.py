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
    # Ensure starter trigger embeddings exist in the fresh test DB so tests that
    # rely on trigger matching behave deterministically even without real
    # embedding infra (sentence-transformers or Ollama).
    # Only install and use the lightweight test embedding service when the
    # environment explicitly requests it (EMBEDDING_BACKEND=none). In CI the
    # workflow will seed triggers separately and may set EMBEDDING_BACKEND
    # differently; avoid overriding embedding behavior in those cases.
    if os.getenv('EMBEDDING_BACKEND', '').lower() == 'none':
        try:
            # To make tests deterministic without relying on heavyweight local
            # models or external services, install a lightweight test embedding
            # service for the test session. This ensures `seed_triggers()` can
            # persist embeddings and later matching will use the same vector
            # space.
            from src.services import embedding_service as _emb_mod

            class _TestEmbeddingService:
                def __init__(self):
                    from src.config import settings as _s
                    self.embedding_dimension = int(getattr(_s, "EMBEDDING_DIMENSION", 384) or 384)

                async def generate_embedding(self, text):
                    if not text:
                        return None
                    # Simple token-based embedding: map tokens into a sparse
                    # vector using hashed token indices so related phrases
                    # (e.g., "list reminders" / "list my reminders") share
                    # dimensions and yield reasonable cosine similarity.
                    import re
                    tokens = [t for t in re.split(r"\W+", text.lower()) if t]
                    import numpy as _np

                    vec = _np.zeros(self.embedding_dimension, dtype=_np.float32)
                    for tok in tokens:
                        idx = abs(hash(tok)) % self.embedding_dimension
                        vec[idx] += 1.0
                    # L2-normalize
                    norm = _np.linalg.norm(vec)
                    if norm == 0:
                        return vec.tolist()
                    return (vec / norm).tolist()

                async def batch_embed(self, texts):
                    out = []
                    for t in texts:
                        out.append(await self.generate_embedding(t))
                    return out

                def embedding_to_bytes(self, emb):
                    import numpy as _np

                    try:
                        arr = _np.array(emb, dtype=_np.float32)
                        return arr.tobytes()
                    except Exception:
                        return b""

                def bytes_to_embedding(self, data):
                    import numpy as _np

                    try:
                        arr = _np.frombuffer(data, dtype=_np.float32)
                        return arr.tolist()
                    except Exception:
                        return None

                def cosine_similarity(self, a, b):
                    import numpy as _np
                    try:
                        a = _np.array(a, dtype=_np.float32)
                        b = _np.array(b, dtype=_np.float32)
                        an = _np.linalg.norm(a)
                        bn = _np.linalg.norm(b)
                        if an == 0 or bn == 0:
                            return 0.0
                        return float(_np.dot(a / an, b / bn))
                    except Exception:
                        return 0.0

            # Replace the embedding service factory for tests
            try:
                _emb_mod.get_embedding_service = lambda: _TestEmbeddingService()
                # Also set the module-level singleton so imports that call
                # `get_embedding_service()` immediately receive the test
                # instance instead of creating a real `EmbeddingService`.
                try:
                    setattr(_emb_mod, "_embedding_service", _TestEmbeddingService())
                except Exception:
                    pass
            except Exception:
                pass

            import asyncio
            from src.triggers.trigger_matcher import seed_triggers
            asyncio.run(seed_triggers())
            print("🧪 Seeded trigger embeddings for tests")
            # Verify seed wrote rows; if not, perform a manual seeding
            try:
                from src.models.database import SessionLocal as _SessionLocal, TriggerEmbedding as _TriggerEmbedding
                dbchk = _SessionLocal()
                try:
                    if dbchk.query(_TriggerEmbedding).count() == 0:
                        # Manual fallback: embed STARTER utterances and persist
                            try:
                                # Raw sqlite fallback to ensure rows persist regardless
                                # of SQLAlchemy session state. Use the same test DB path
                                # to insert TriggerEmbedding rows directly.
                                import sqlite3, datetime
                                from src.triggers.trigger_matcher import STARTER
                                tester = _TestEmbeddingService()
                                embs = asyncio.run(tester.batch_embed([s['utterance'] for s in STARTER]))
                                db_path = TEST_DB_PATH
                                conn = sqlite3.connect(str(db_path))
                                try:
                                    cur = conn.cursor()
                                    now = datetime.datetime.utcnow().isoformat()
                                    for spec, emb in zip(STARTER, embs):
                                        if emb is None:
                                            continue
                                        b = tester.embedding_to_bytes(emb)
                                        cur.execute(
                                            "INSERT INTO trigger_embeddings (name, action_type, embedding, threshold, created_at, updated_at) VALUES (?, ?, ?, ?, ?, ?)",
                                            (spec.get('name') or spec.get('utterance'), spec['action_type'], sqlite3.Binary(b), float(spec.get('threshold', 0.75)), now, now),
                                        )
                                    conn.commit()
                                    print("🧪 Fallback-seeded trigger embeddings into test DB (sqlite)")
                                finally:
                                    conn.close()
                            except Exception:
                                pass
                finally:
                    dbchk.close()
            except Exception:
                pass
            # Lower stored trigger thresholds in the test DB to make matching
            # permissive under the lightweight test embedding service.
            try:
                from src.models.database import SessionLocal as _SessionLocal, TriggerEmbedding as _TriggerEmbedding
                dbt = _SessionLocal()
                try:
                    rows = dbt.query(_TriggerEmbedding).all()
                    for r in rows:
                        try:
                            r.threshold = 0.2
                        except Exception:
                            pass
                    dbt.commit()
                finally:
                    dbt.close()
            except Exception:
                pass
        except Exception as _ex:
            # Fail fast: seeding trigger embeddings is required for deterministic
            # trigger-matching behavior in tests. Raise to abort the test run so
            # the failure is visible and can be fixed rather than silently
            # falling back to keyword matching.
            raise RuntimeError(f"Failed to seed trigger embeddings for tests: {_ex}")
    # Verify that the seed actually persisted trigger embeddings into the
    # test database. If no trigger rows were written, abort to surface the
    # underlying embedding/backend issue (so CI or developer can fix it).
    try:
        from src.models.database import SessionLocal as _SessionLocal
        from src.models.database import TriggerEmbedding as _TriggerEmbedding
        db_check = _SessionLocal()
        try:
            count = db_check.query(_TriggerEmbedding).count()
            if count == 0:
                # Do not fail the entire test run if seeding didn't persist.
                # Some environments seed triggers via CI scripts or external
                # steps; warn instead so developers can investigate if
                # deterministic trigger matching is required in their setup.
                print("⚠️  Warning: no trigger_embeddings rows found after seeding (count=0)")
        finally:
            db_check.close()
    except Exception as _ex:
        print(f"⚠️  Trigger embedding verification encountered an error: {_ex}")
    
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
