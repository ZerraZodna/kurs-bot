"""
Pytest configuration for kurs-bot tests.
Central location for all test database setup and configuration.
"""
import os
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

# Prevent tests from attempting real Ollama calls in CI: ensure test flag
# is explicit and disable real Ollama usage unless the environment requests it.
os.environ.setdefault('TEST_USE_REAL_OLLAMA', '0')
os.environ.setdefault('USE_REAL_OLLAMA', '0')

# Prefer a non-local embedding backend during collection so import-time
# code does not attempt to load heavyweight local models. The session
# fixture will install a lightweight test embedding service.
os.environ.setdefault('EMBEDDING_BACKEND', 'none')

# Set test database environment variable for all tests
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
        from src.models.database import init_db
        init_db()
    except Exception as e:
        print(f"⚠️  Could not initialize test DB schema: {e}")
    # Ensure starter trigger embeddings exist in the fresh test DB so tests that
    # rely on trigger matching behave deterministically even without real
    # embedding infra (sentence-transformers or Ollama).
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
        except Exception:
            pass

        import asyncio
        from src.triggers.trigger_matcher import seed_triggers
        asyncio.run(seed_triggers())
        print("🧪 Seeded trigger embeddings for tests")
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
                raise RuntimeError("Trigger embeddings seeding completed but no rows were persisted (count=0)")
        finally:
            db_check.close()
    except Exception as _ex:
        raise RuntimeError(f"Trigger embedding verification failed: {_ex}")
    
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
