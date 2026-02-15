"""
Pytest configuration for kurs-bot tests.
Central location for all test database setup and configuration.
"""
import os
import time
from pathlib import Path
import pytest

# Test database configuration (single source of truth)
TEST_DB_PATH = Path('src/data/test.db')
TEST_DB_URL = f'sqlite:///{TEST_DB_PATH}'

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
        import asyncio
        from src.triggers.trigger_matcher import seed_triggers
        asyncio.run(seed_triggers())
        print("🧪 Seeded trigger embeddings for tests")
    except Exception as _ex:
        print(f"⚠️ Could not seed trigger embeddings for tests: {_ex}")
    
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
