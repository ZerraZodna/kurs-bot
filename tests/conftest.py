"""
Pytest configuration and global fixtures.

This module provides:
- Import-time blocking of Ollama/faiss for fast test collection
- Dotenv loading for test environment variables
- Database initialization and cleanup
- Global mock fixtures
- HTTP request blocking for test safety
"""

import os
from pathlib import Path

import pytest


# Load dotenv early so its variables are available to pytest and any imported
# project modules during collection
def _load_dotenv_if_present():
    repo_root = Path(__file__).resolve().parent
    env_path = repo_root / ".env.test"
    if not env_path.exists():
        return
    try:
        with env_path.open("r", encoding="utf8") as f:
            for raw in f:
                line = raw.strip()
                if not line or line.startswith("#"):
                    continue
                if "=" not in line:
                    continue
                k, v = line.split("=", 1)
                k = k.strip()
                v = v.strip().strip('"')
                if k and os.getenv(k) is None:
                    os.environ[k] = v
    except Exception:
        pass


_load_dotenv_if_present()

# Register fake modules at import time to prevent real initialization
from mocks.ollama_mock import register_fake_ollama

register_fake_ollama()

# Import all models first to populate Base.metadata registry
from src.models.database import Base

# Model imports populate registry before fixtures load


# Auto-import fixture modules (after model registry populated)
pytest_plugins = [
    "tests.fixtures.database",
    "tests.fixtures.users",
    "tests.fixtures.services",
]

# Ensure all models are registered for test DB schema creation


# Prevent accidental outbound HTTP requests to Ollama during tests unless
# TEST_USE_REAL_OLLAMA is set. This guard raises if any code attempts to
# contact the local or cloud Ollama endpoints.
@pytest.fixture(scope="session", autouse=True)
def _block_ollama_http_requests():
    v = os.getenv("TEST_USE_REAL_OLLAMA")
    if v and str(v).strip().lower() in ("1", "true", "yes", "y"):
        yield
        return

    try:
        import httpx

        LOCAL = os.getenv("LOCAL_OLLAMA_URL", "http://localhost:11434")
        CLOUD = os.getenv("CLOUD_OLLAMA_URL", "https://ollama.com")

        def _is_ollama_url(u: object) -> bool:
            try:
                s = str(u)
            except Exception:
                return False
            return LOCAL in s or CLOUD in s or "ollama.com" in s or "localhost:11434" in s

        _orig_async_request = getattr(httpx.AsyncClient, "request", None)
        _orig_sync_request = getattr(httpx.Client, "request", None)
        _orig_module_request = getattr(httpx, "request", None)

        async def _async_request(self, method, url, *args, **kwargs):
            if _is_ollama_url(url):
                raise RuntimeError(
                    "Blocked outgoing HTTP request to Ollama in tests (enable with TEST_USE_REAL_OLLAMA=1)"
                )
            return await _orig_async_request(self, method, url, *args, **kwargs)

        def _sync_request(self, method, url, *args, **kwargs):
            if _is_ollama_url(url):
                raise RuntimeError(
                    "Blocked outgoing HTTP request to Ollama in tests (enable with TEST_USE_REAL_OLLAMA=1)"
                )
            return _orig_sync_request(self, method, url, *args, **kwargs)

        def _module_request(method, url, *args, **kwargs):
            if _is_ollama_url(url):
                raise RuntimeError(
                    "Blocked outgoing HTTP request to Ollama in tests (enable with TEST_USE_REAL_OLLAMA=1)"
                )
            return _orig_module_request(method, url, *args, **kwargs)

        httpx.AsyncClient.request = _async_request
        httpx.Client.request = _sync_request
        httpx.request = _module_request
    except Exception:
        _orig_async_request = _orig_sync_request = _orig_module_request = None

    yield

    # Restore originals at session end
    try:
        import httpx as _httpx

        if _orig_async_request is not None:
            _httpx.AsyncClient.request = _orig_async_request
        if _orig_sync_request is not None:
            _httpx.Client.request = _orig_sync_request
        if _orig_module_request is not None:
            _httpx.request = _orig_module_request
    except Exception:
        pass


# Block external HTTP requests unless TEST_USE_REAL_OLLAMA=1
@pytest.fixture(autouse=True)
def block_external_http():
    """Block accidental Ollama calls unless TEST_USE_REAL_OLLAMA=1."""
    if os.getenv("TEST_USE_REAL_OLLAMA"):
        yield
        return
    orig_request = None
    try:
        import httpx

        LOCAL = "localhost:11434"
        CLOUD = "ollama.com"

        def is_ollama_url(u):
            s = str(u)
            return LOCAL in s or CLOUD in s

        orig_request = httpx.request

        def blocked_request(method, url, *args, **kwargs):
            if is_ollama_url(url):
                raise RuntimeError("Blocked Ollama HTTP in tests (set TEST_USE_REAL_OLLAMA=1)")
            return orig_request(method, url, *args, **kwargs)

        httpx.request = blocked_request
    except Exception:
        pass
    yield
    try:
        import httpx

        if orig_request:
            httpx.request = orig_request
    except Exception:
        pass


@pytest.fixture(autouse=True)
def ensure_test_db(db_engine, monkeypatch):
    """Provide a fast per-test DB by recreating schema.

    Recreates DB schema for isolation. Trigger seeding removed in Phase 3
    as embedding-based trigger matching was replaced by function calling.

    Uses the worker-aware db_engine fixture to support pytest-xdist parallel
    execution. Also patches SessionLocal to use the worker-specific engine.

    Patches all locations where SessionLocal is imported to ensure they use
    the worker-specific database during parallel test execution.
    """
    # Patch SessionLocal to use the worker-specific engine
    from sqlalchemy.orm import sessionmaker

    TestSessionLocal = sessionmaker(bind=db_engine, autoflush=False, autocommit=False, future=True)

    # Patch all locations where SessionLocal is imported directly
    # This ensures parallel test execution works correctly with pytest-xdist
    monkeypatch.setattr("src.models.database.SessionLocal", TestSessionLocal)
    monkeypatch.setattr("src.scheduler.SessionLocal", TestSessionLocal)
    monkeypatch.setattr("src.scheduler.manager.SessionLocal", TestSessionLocal)
    monkeypatch.setattr("src.scheduler.maintenance.SessionLocal", TestSessionLocal)
    monkeypatch.setattr("src.scheduler.job_state.SessionLocal", TestSessionLocal)
    monkeypatch.setattr("src.memories.manager.SessionLocal", TestSessionLocal)
    monkeypatch.setattr("src.integrations.telegram.SessionLocal", TestSessionLocal)
    monkeypatch.setattr("src.api.dialogue_routes.SessionLocal", TestSessionLocal)
    monkeypatch.setattr("src.api.dev_web_client.SessionLocal", TestSessionLocal)
    monkeypatch.setattr("src.api.gdpr_routes.SessionLocal", TestSessionLocal)
    monkeypatch.setattr("src.api.app.SessionLocal", TestSessionLocal)
    monkeypatch.setattr("src.services.dialogue.command_handlers.SessionLocal", TestSessionLocal)
    monkeypatch.setattr("src.services.maintenance.SessionLocal", TestSessionLocal)
    monkeypatch.setattr("src.middleware.consent.SessionLocal", TestSessionLocal)
    monkeypatch.setattr("src.language.prompt_registry.SessionLocal", TestSessionLocal)

    # Skip app startup lessons import in tests
    monkeypatch.setattr("src.api.app.ensure_lessons_imported", lambda: None, raising=False)

    repo_root = Path(__file__).resolve().parents[1]

    # Always drop_all + create_all for reliable test isolation (fixes SQLite truncation issues in CI)
    Base.metadata.drop_all(bind=db_engine)
    Base.metadata.create_all(bind=db_engine)
    print("Recreated test DB schema")

    yield


@pytest.fixture(autouse=True)
def per_test_cleanup():
    """Run after each test to attempt to close background services and
    trigger gc so sockets/event-loops are released promptly.
    """
    yield

    # Clear AI Judge cache before/after each test to ensure tests call Ollama
    try:
        from src.memories.cache import DecisionCache

        cache = DecisionCache()
        cache.clear()
    except Exception:
        pass

    # Robust scheduler cleanup: remove all jobs then shutdown
    try:
        from src.scheduler.lifecycle import get_scheduler, shutdown_scheduler

        scheduler = get_scheduler()
        if scheduler:
            try:
                scheduler.remove_all_jobs()
                print("Cleared all APScheduler jobs")
            except Exception:
                pass
            try:
                shutdown_scheduler()
            except Exception:
                pass
    except Exception:
        pass

    # Close embedding service instance if present
    try:
        import importlib

        emb_mod = importlib.import_module("src.services.embedding_service")
        svc = getattr(emb_mod, "_embedding_service", None)
        if svc is not None:
            try:
                import asyncio

                asyncio.run(svc.close())
            except Exception:
                pass
    except Exception:
        pass

    # Force garbage collection to run destructors for sockets/loops
    try:
        import gc
        import warnings as _warnings

        # Suppress ResourceWarning during gc.collect so pytest (running with
        # -W error) doesn't convert unraisable destructor warnings into
        # test errors while we continue to harden background-service cleanup.
        with _warnings.catch_warnings():
            _warnings.filterwarnings("ignore", category=ResourceWarning)
            gc.collect()
    except Exception:
        pass


@pytest.fixture(scope="session", autouse=True)
def session_teardown():
    """Session-level teardown to clean up global background services that
    may be started during tests (scheduler, embedding service). This ensures
    threads, event loops and any persistent HTTP clients are closed at the
    end of the test session to avoid ResourceWarnings when pytest runs with
    warnings-as-errors.
    """
    yield
    # Shutdown APScheduler if it was started
    try:
        from src.scheduler.core import SchedulerService

        try:
            SchedulerService.shutdown()
        except Exception:
            pass
    except Exception:
        pass

    # Close embedding service if it was instantiated
    try:
        import importlib

        emb_mod = importlib.import_module("src.services.embedding_service")
        svc = getattr(emb_mod, "_embedding_service", None)
        if svc is not None:
            try:
                import asyncio

                asyncio.run(svc.close())
            except Exception:
                pass
    except Exception:
        pass


# Module-scoped DB schema creation (idempotent - safe to call multiple times)
@pytest.fixture(scope="module", autouse=True)
def module_db_setup(db_engine):
    """Module-scoped DB schema creation (idempotent - safe to call multiple times)."""
    from sqlalchemy import text
    from sqlalchemy.exc import OperationalError

    # Drop all tables first to ensure clean state (handles parallel test conflicts)
    # Using DROP TABLE IF EXISTS instead of drop_all to avoid transaction issues
    try:
        with db_engine.connect() as conn:
            # Get list of all tables to drop
            result = conn.execute(text("SELECT name FROM sqlite_master WHERE type='table'"))
            tables = [row[0] for row in result.fetchall()]

            # Drop all tables except sqlite_schema (internal)
            for table in tables:
                if table != "sqlite_schema":
                    try:
                        conn.execute(text(f"DROP TABLE IF EXISTS {table}"))
                    except OperationalError:
                        pass  # Table doesn't exist, OK

            conn.commit()
    except Exception:
        # If connection fails, just continue - create_all will recreate tables
        pass

    # Now create all tables fresh
    Base.metadata.create_all(db_engine)

    yield
    # No cleanup needed - temp DB is discarded after module


# Fast per-test cleanup: DELETE FROM all tables (handles all schema tables). Safe if tables missing.
@pytest.fixture(scope="function", autouse=True)
def truncate_test_tables(db_engine):
    """Fast per-test cleanup: DELETE FROM all tables (handles all schema tables). Safe if tables missing."""
    from sqlalchemy import text, inspect
    from sqlalchemy.exc import OperationalError

    with db_engine.connect() as conn:
        # Get all tables to truncate
        inspector = inspect(db_engine)
        all_tables = inspector.get_table_names()

        # Truncate all tables
        for table in all_tables:
            try:
                # Use DELETE instead of TRUNCATE to preserve auto-increment values
                conn.execute(text(f"DELETE FROM {table}"))
            except OperationalError as e:
                # Table doesn't exist or other error - ignore
                if "already exists" not in str(e).lower() and "no such table" not in str(e).lower():
                    print(f"Warning: Error truncating {table}: {e}")
                pass
        conn.commit()


# Serial test handling - collect serial tests last so they run in isolation
def pytest_collection_modifyitems(config, items):
    serial_items = [i for i in items if i.get_closest_marker("serial")]
    other_items = [i for i in items if not i.get_closest_marker("serial")]
    items[:] = other_items + serial_items


# Model overrides for test configuration
def pytest_configure(config):
    defaults_model = "llama3.2:3b"
    overrides = {
        "OLLAMA_MODEL": os.getenv("TEST_OLLAMA_MODEL", defaults_model),
        "NON_ENGLISH_OLLAMA_MODEL": os.getenv("TEST_NON_ENGLISH_OLLAMA_MODEL", defaults_model),
    }
    changed = False
    for k, v in overrides.items():
        if v.endswith(":test"):
            v = defaults_model
        os.environ[k] = v
        changed = True
    if changed:
        try:
            import importlib

            import src.config as cfg

            importlib.reload(cfg)
            print("🔧 Test Ollama model overrides applied")
        except Exception:
            pass
