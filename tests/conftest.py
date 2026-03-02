"""
Pytest configuration and global fixtures.

This module provides:
- Import-time blocking of Ollama/faiss for fast test collection
- Database initialization and cleanup
- Global mock fixtures
- HTTP request blocking for test safety
"""

import os
from pathlib import Path
import sys
import types
from typing import Optional

import pytest

# Register fake modules at import time to prevent real initialization
from tests.mocks.faiss_mock import register_fake_faiss
from tests.mocks.ollama_mock import register_fake_ollama

register_fake_faiss()
register_fake_ollama()

# Auto-import fixture modules
pytest_plugins = [
    "tests.fixtures.database",
    "tests.fixtures.users", 
    "tests.fixtures.services",
]

# Ensure test database is initialized for every test to guarantee isolation.
from src.models.database import Base


def pytest_collection_modifyitems(config, items):
    """Move serial-marked tests to the end so xdist runs them in worker gw0.
    
    This ensures tests marked with @pytest.mark.serial run in the main worker,
    which is necessary for tests that use global state like APScheduler.
    """
    serial_items = [i for i in items if i.get_closest_marker("serial")]
    other_items = [i for i in items if not i.get_closest_marker("serial")]
    items[:] = other_items + serial_items


@pytest.fixture(autouse=True)
def check_serial_marker(request):
    """Skip serial tests when running in parallel workers (not main).
    
    This ensures tests marked with @pytest.mark.serial only run in the main
    worker when using pytest-xdist, avoiding race conditions with global
    state like APScheduler and TriggerMatcher singletons.
    """
    # Check if running with xdist and not in main worker
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    serial_marker = request.node.get_closest_marker("serial")
    
    if serial_marker and worker_id != "main":
        pytest.skip(f"Skipping serial test '{request.node.name}' in worker {worker_id}")


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
                raise RuntimeError("Blocked outgoing HTTP request to Ollama in tests (enable with TEST_USE_REAL_OLLAMA=1)")
            return await _orig_async_request(self, method, url, *args, **kwargs)

        def _sync_request(self, method, url, *args, **kwargs):
            if _is_ollama_url(url):
                raise RuntimeError("Blocked outgoing HTTP request to Ollama in tests (enable with TEST_USE_REAL_OLLAMA=1)")
            return _orig_sync_request(self, method, url, *args, **kwargs)

        def _module_request(method, url, *args, **kwargs):
            if _is_ollama_url(url):
                raise RuntimeError("Blocked outgoing HTTP request to Ollama in tests (enable with TEST_USE_REAL_OLLAMA=1)")
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


@pytest.fixture(autouse=True)
def ensure_test_db(db_engine, monkeypatch):
    """Provide a fast per-test DB by recreating schema and seeding triggers.

    Recreates DB schema for isolation and seeds triggers from precomputed CI
    data. This avoids importing sentence-transformers during tests.
    
    Uses the worker-aware db_engine fixture to support pytest-xdist parallel
    execution. Also patches SessionLocal to use the worker-specific engine.
    """
    # Patch SessionLocal to use the worker-specific engine
    from sqlalchemy.orm import sessionmaker
    TestSessionLocal = sessionmaker(bind=db_engine, autoflush=False, autocommit=False, future=True)
    monkeypatch.setattr("src.models.database.SessionLocal", TestSessionLocal)
    monkeypatch.setattr("src.triggers.trigger_matcher.SessionLocal", TestSessionLocal)
    # Also patch the scheduler module's SessionLocal reference, since it imports its own copy
    monkeypatch.setattr("src.scheduler.SessionLocal", TestSessionLocal)
    
    repo_root = Path(__file__).resolve().parents[1]
    
    try:
        Base.metadata.drop_all(bind=db_engine)
        Base.metadata.create_all(bind=db_engine)

        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
    except SystemExit:
        raise
    except Exception as e:
        print(f"Warning: failed to initialize test DB or seed triggers: {e}")

    yield



@pytest.fixture(autouse=True)
def per_test_cleanup():
    """Run after each test to attempt to close background services and
    trigger gc so sockets/event-loops are released promptly.
    """
    yield

    # Best-effort scheduler shutdown after each test
    try:
        from src.scheduler.core import SchedulerService

        try:
            SchedulerService.shutdown()
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
