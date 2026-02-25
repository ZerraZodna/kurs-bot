# Optional: Parallel Test Execution with pytest-xdist

**Status**: Not yet implemented — optional speed-up  
**Estimated gain**: 40–60% reduction in total test run time  
**Risk**: Medium — requires DB isolation fixes and serial markers on stateful tests

---

## Overview

The test suite currently runs sequentially. Adding `pytest-xdist` allows tests to run across multiple CPU workers in parallel. This is optional because:

- The current SQLite template-DB approach needs per-worker isolation
- Scheduler tests use global `APScheduler` state that is not worker-safe
- The suite already runs in a reasonable time (~30s); parallelism matters most as the suite grows

---

## Prerequisites

Before enabling parallel execution, two conditions must be true:

1. **Each worker gets its own database file** — workers cannot share a single SQLite file
2. **Stateful tests are marked `serial`** — scheduler init/shutdown and any test that patches global singletons must run in a single worker

---

## Step 1 — Install pytest-xdist

Add to `requirements.txt` (dev section or a separate `requirements-dev.txt`):

```
pytest-xdist
```

Install:

```bash
pip install pytest-xdist
```

---

## Step 2 — Register the `serial` Mark

Add to `pytest.ini` so the mark is recognised without warnings:

```ini
[pytest]
norecursedirs = scripts/debug
testpaths = tests
filterwarnings =
    ignore:urllib3 v2 only supports OpenSSL
    ignore:builtin type SwigPyPacked has no __module__ attribute:DeprecationWarning
    ignore:builtin type SwigPyObject has no __module__ attribute:DeprecationWarning
    ignore:builtin type swigvarlink has no __module__ attribute:DeprecationWarning
markers =
    serial: mark test to run in the main worker only (not parallelised)
```

---

## Step 3 — Per-Worker Database Isolation

The current `conftest.py` creates a single SQLite template DB. With multiple workers each worker needs its own copy.

Replace the `db_engine` fixture in `tests/fixtures/database.py` (or `tests/conftest.py`) with a worker-aware version:

```python
import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# pytest-xdist injects the worker id via the PYTEST_XDIST_WORKER env var.
# Falls back to "main" when running without xdist.

@pytest.fixture(scope="session")
def db_engine(tmp_path_factory):
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    # Each worker gets its own temp directory → no file contention
    db_dir = tmp_path_factory.mktemp(f"db_{worker_id}")
    db_path = db_dir / "test.db"
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    # Create schema once per worker
    from src.models.database import Base
    Base.metadata.create_all(engine)
    yield engine
    engine.dispose()
```

> **Why `tmp_path_factory`?**  
> It is session-scoped and xdist-safe. Each worker receives a unique base temp directory, so DB files never collide.

---

## Step 4 — Mark Non-Parallel-Safe Tests

Apply `@pytest.mark.serial` to any test that:

- Initialises or shuts down the global `APScheduler` instance
- Patches a module-level singleton (e.g. `MemoryManager._instance`)
- Relies on test execution order

### Known tests that need `@pytest.mark.serial`

| File | Reason |
|------|--------|
| `tests/unit/onboarding/test_onboarding_scheduling.py` | Starts/stops scheduler |
| `tests/unit/onboarding/test_onboarding_service_integration.py` | Uses scheduler fixture |
| Any test using `scheduler_service` fixture | Global APScheduler state |

Example:

```python
import pytest

@pytest.mark.serial
class TestOnboardingScheduling:
    """Tests that touch the global scheduler — must run serially."""

    def test_schedule_created_after_onboarding(self, db_session, test_user):
        ...
```

---

## Step 5 — Configure xdist to Respect `serial`

Add a `conftest.py` hook so `serial`-marked tests are collected by the main worker:

```python
# tests/conftest.py  (add at module level)

def pytest_collection_modifyitems(config, items):
    """Move serial-marked tests to the end so xdist runs them in worker gw0."""
    serial_items = [i for i in items if i.get_closest_marker("serial")]
    other_items  = [i for i in items if not i.get_closest_marker("serial")]
    items[:] = other_items + serial_items
```

> **Note**: For strict single-worker enforcement, use the `pytest-xdist-serial` plugin or run serial tests in a separate `pytest` invocation (see CI section below).

---

## Step 6 — Running Parallel Tests

```bash
# Auto-detect CPU count
pytest -n auto

# Explicit worker count (recommended: leave 1–2 cores free)
pytest -n 4

# Run only parallel-safe tests
pytest -n auto -m "not serial"

# Run serial tests separately (for CI)
pytest -m serial
```

---

## Step 7 — CI Integration

Split the test run into two steps to keep serial tests isolated:

```yaml
# Example GitHub Actions step
- name: Run parallel tests
  run: pytest -n auto -m "not serial" --cov=src --cov-report=xml

- name: Run serial tests
  run: pytest -m serial --cov=src --cov-append --cov-report=xml
```

---

## Troubleshooting

### `sqlite3.OperationalError: database is locked`
Workers are sharing the same DB file. Ensure the `db_engine` fixture uses `PYTEST_XDIST_WORKER` to create separate files (Step 3).

### `AssertionError` in scheduler tests after parallelising
The scheduler fixture is not worker-safe. Add `@pytest.mark.serial` to the affected test class/function (Step 4).

### Coverage is incomplete when using `-n auto`
Use `--cov-append` on the serial run and combine reports, or use `pytest-cov`'s built-in xdist support (it handles this automatically in recent versions).

### Tests pass alone but fail in parallel
Usually a shared global state issue. Run with `-n 2` first to narrow down, then add `@pytest.mark.serial`.

---

## Expected Impact

| Metric | Before | After (estimated) |
|--------|--------|-------------------|
| Total test time | ~30s | ~12–18s |
| Worker count | 1 | 4 (on typical dev machine) |
| Serial test count | all | ~10–15 tests |
| Parallel test count | 0 | ~195+ tests |

---

## Related

- `tests/README.md` — general test suite documentation
- `docs/TEST_REFACTORING_PLAN.md` — full refactoring history
- [pytest-xdist docs](https://pytest-xdist.readthedocs.io/)
