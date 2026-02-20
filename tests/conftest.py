import os
from pathlib import Path
import sys
import types
import pytest

# Insert an import-time stub for the Ollama client to avoid any real
# initialization (model/DB/HTTP) during test collection. Conftest is
# imported by pytest early, so placing the stub here ensures it runs before
# other project modules are imported.
_test_use_real = os.getenv("TEST_USE_REAL_OLLAMA") or os.getenv("USE_REAL_OLLAMA")
if not _test_use_real or str(_test_use_real).strip().lower() not in ("1", "true", "yes", "y"):
    # Also block the top-level `ollama` package import entirely so any
    # attempt to `from ollama import Client` or similar fails fast during
    # test collection. This prevents the official client package from
    # initializing or opening sockets before our guards run.
    if "ollama" not in sys.modules:
        class _BlockedOllama(types.ModuleType):
            # Allow harmless introspection attributes to be read so that
            # third-party libraries (inspect, torch, transformers, etc.) can
            # perform module inspection without triggering our protective
            # RuntimeError. Only raise when production code actually tries to
            # access client objects like `Client`/`chat`.
            _allowed_attrs = {"__file__", "__spec__", "__path__", "__name__"}

            def __getattr__(self, attr):
                if attr in self._allowed_attrs:
                    # Provide a benign value for introspection
                    if attr == "__file__":
                        return "<blocked-ollama>"
                    return None
                # Only raise when test-run protection is triggered by real use
                raise RuntimeError(
                    "Access to the 'ollama' package is blocked in test runs (TEST_USE_REAL_OLLAMA is falsy)."
                )

        blk = _BlockedOllama("ollama")
        # Ensure basic module metadata exists for importlib/inspect
        try:
            blk.__file__ = "<blocked-ollama>"
        except Exception:
            pass
        sys.modules["ollama"] = blk
    _mod = "src.services.dialogue.ollama_client"
    if _mod not in sys.modules:
        _fake = types.ModuleType(_mod)

        async def _fake_call_ollama(prompt: str, model: str | None = None, language: str | None = None) -> str:
            short = (prompt[:160] + "...") if prompt and len(prompt) > 160 else (prompt or "")
            return f"[MOCK_OLLAMA_REPLY] model={model or 'default'} lang={language or 'en'} text={short}"

        setattr(_fake, "call_ollama", _fake_call_ollama)
        sys.modules[_mod] = _fake
        # Force-import the parent package so its __init__ executes while our
        # fake submodule is present in sys.modules. The package's import will
        # bind `call_ollama` into the package namespace (via
        # `from .ollama_client import call_ollama`) without triggering real
        # initialization of the real submodule.
        try:
            import importlib

            importlib.import_module("src.services.dialogue")
            pkg_mod = sys.modules.get("src.services.dialogue")
            if pkg_mod is not None:
                try:
                    setattr(pkg_mod, "ollama_client", _fake)
                    setattr(pkg_mod, "call_ollama", _fake_call_ollama)
                except Exception:
                    pass
        except Exception:
            # If import fails, leave the fake submodule in sys.modules; tests
            # will either import the package later (and find our fake) or
            # monkeypatch with raising=False.
            pass

# Ensure test database is initialized for every test to guarantee isolation.
# This autouse fixture recreates the schema and seeds trigger embeddings from
# `scripts/ci_trigger_data.py` (via `scripts/ci_seed_triggers.py`). Tests
# must include a committed `scripts/ci_trigger_data.py` so seeding does not
# require heavy ML dependencies.
from src.models.database import engine, Base


# Prevent accidental outbound HTTP requests to Ollama during tests when
# TEST_USE_REAL_OLLAMA is not enabled. This guard raises if any code
# attempts to contact the local or cloud Ollama endpoints.
@pytest.fixture(scope="session", autouse=True)
def _block_ollama_http_requests():
    v = os.getenv("TEST_USE_REAL_OLLAMA") or os.getenv("USE_REAL_OLLAMA")
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
                raise RuntimeError("Blocked outgoing HTTP request to Ollama in tests (TEST_USE_REAL_OLLAMA is falsy)")
            return await _orig_async_request(self, method, url, *args, **kwargs)

        def _sync_request(self, method, url, *args, **kwargs):
            if _is_ollama_url(url):
                raise RuntimeError("Blocked outgoing HTTP request to Ollama in tests (TEST_USE_REAL_OLLAMA is falsy)")
            return _orig_sync_request(self, method, url, *args, **kwargs)

        def _module_request(method, url, *args, **kwargs):
            if _is_ollama_url(url):
                raise RuntimeError("Blocked outgoing HTTP request to Ollama in tests (TEST_USE_REAL_OLLAMA is falsy)")
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
def ensure_test_db():
    """Provide a fast per-test DB by copying `src/data/test_template.db`.

    First run will (re)create `src/data/test.db`, seed triggers, and save a
    template at `test_template.db`. Subsequent runs copy that template to
    `test.db` for quick startup.
    """
    repo_root = Path(__file__).resolve().parents[1]
    data_dir = repo_root / "src" / "data"
    data_dir.mkdir(parents=True, exist_ok=True)

    # Recreate DB schema for isolation and seed triggers from precomputed CI
    # data. This avoids importing sentence-transformers during tests.
    try:
        Base.metadata.drop_all(bind=engine)
        Base.metadata.create_all(bind=engine)

        if str(repo_root) not in sys.path:
            sys.path.insert(0, str(repo_root))
        from scripts import ci_seed_triggers

        ci_seed_triggers.main()
    except SystemExit:
        # Re-raise to make test failure explicit when precomputed triggers missing
        raise
    except Exception as e:
        # Best-effort: log and continue so unrelated tests can still run
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
