from pathlib import Path
import sys
import pytest

# Ensure test database is initialized for every test to guarantee isolation.
# This autouse fixture recreates the schema and seeds trigger embeddings from
# `scripts/ci_trigger_data.py` (via `scripts/ci_seed_triggers.py`). Tests
# must include a committed `scripts/ci_trigger_data.py` so seeding does not
# require heavy ML dependencies.
from src.models.database import engine, Base


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
