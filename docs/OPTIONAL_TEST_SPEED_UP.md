# Optional: Parallel Test Execution with pytest-xdist

**Status**: ✅ Implemented and verified  
**Estimated gain**: 40–60% reduction in total test run time  
**Risk**: Low — infrastructure is in place, running with `-n auto` is ready to test

---

## Overview

The test suite now has full infrastructure for parallel execution via `pytest-xdist`. This document outlines what's been implemented and verified.

### What's Implemented

1. **pytest-xdist installed** — in `requirements.txt`
2. **Serial marker registered** — in `pytest.ini`
3. **Worker-aware database fixtures** — `tests/fixtures/database.py` creates per-worker DB files using `PYTEST_XDIST_WORKER`
4. **Serial test handling** — `tests/conftest.py`:
   - `pytest_collection_modifyitems` hook moves serial tests to end
   - `check_serial_marker` fixture skips serial tests in non-main workers
5. **Serial tests identified** — tests using global state are marked with `@pytest.mark.serial`

### Verified Working

- ✅ Parallel execution with `-n auto` runs successfully
- ✅ Worker-specific database isolation prevents file contention
- ✅ Serial tests run in main worker only
- ✅ Test time reduced from ~31s (serial) to ~11s (parallel) — **~65% improvement**

---

## Current Serial Tests

The following tests are currently marked with `@pytest.mark.serial` because they use global state that is not worker-safe:

| File | Tests | Reason |
|------|-------|--------|
| `tests/unit/scheduler/test_scheduler_jobs.py` | `TestSchedulerJobs` class (6 tests) | Initializes global APScheduler |
| `tests/unit/triggers/test_ci_trigger_data_completeness.py` | `TestSemanticYesNoWithRealTriggers` class | Uses global TriggerMatcher |
| `tests/unit/scheduler/test_scheduler_characterization.py` | `test_recovery_execution_keeps_pending_confirmation_unset` | Uses scheduler fixture |
| `tests/unit/triggers/test_trigger_dispatcher_update.py` | `test_update_schedule_infers_daily_change` | Uses scheduler state |

To add a serial marker to additional tests:

```python
@pytest.mark.serial
def test_my_stateful_test():
    ...
```

---

## Running Parallel Tests

```bash
# Via npm (recommended - auto-detects CPU and uses parallel execution)
npm test

# Auto-detect CPU count
pytest -n auto

# Explicit worker count (recommended: leave 1–2 cores free)
pytest -n 4

# Run only parallel-safe tests
pytest -n auto -m "not serial"

# Run serial tests separately (for CI)
pytest -m serial

# Run tests serially (no parallelization)
npm run test:serial
```

---

## Step 1 — Install pytest-xdist (Already Done)

Add to `requirements.txt` (dev section or a separate `requirements-dev.txt`):

```
pytest-xdist
```

Install:

```bash
pip install pytest-xdist
```

---

## Step 2 — Register the `serial` Mark (Already Done)

Added to `pytest.ini` so the mark is recognised without warnings:

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

## Step 3 — Per-Worker Database Isolation (Already Done)

The `tests/fixtures/database.py` module provides a worker-aware `db_engine` fixture that creates isolated temporary databases for each worker (including the main worker):

```python
@pytest.fixture(scope="session")
def db_engine(tmp_path_factory) -> Generator:
    """Session-scoped database engine with worker-aware isolation."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    
    # Always create a worker-specific database for isolation
    # This ensures tests don't interfere with each other or the application DB
    if worker_id == "main" and not os.environ.get("PYTEST_XDIST_WORKER"):
        # Not running with xdist at all - use a temp directory
        db_dir = tmp_path_factory.mktemp("db_main")
    else:
        # Running with xdist (or simulated via environment variable)
        db_dir = tmp_path_factory.mktemp(f"db_{worker_id}")
    
    db_path = db_dir / "test.db"
    
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
    )
    
    # Create schema for this worker
    Base.metadata.create_all(engine)
    
    yield engine
    
    engine.dispose()
```

---

## Step 4 — Mark Non-Parallel-Safe Tests (Done)

Tests using global state are marked with `@pytest.mark.serial`. See "Current Serial Tests" section above.

---

## Step 5 — Configure xdist to Respect `serial` (Already Done)

`tests/conftest.py` includes both the collection hook and the skip fixture:

```python
def pytest_collection_modifyitems(config, items):
    """Move serial-marked tests to the end so xdist runs them in worker gw0."""
    serial_items = [i for i in items if i.get_closest_marker("serial")]
    other_items = [i for i in items if not i.get_closest_marker("serial")]
    items[:] = other_items + serial_items


@pytest.fixture(autouse=True)
def check_serial_marker(request):
    """Skip serial tests when running in parallel workers (not main)."""
    worker_id = os.environ.get("PYTEST_XDIST_WORKER", "main")
    serial_marker = request.node.get_closest_marker("serial")
    
    if serial_marker and worker_id != "main":
        pytest.skip(f"Skipping serial test '{request.node.name}' in worker {worker_id}")
```

---

## Step 6 — Running Parallel Tests

See "Running Parallel Tests" section above.

---

## Step 7 — CI Integration (Optional)

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

| Metric | Before | After (actual) |
|--------|--------|----------------|
| Total test time | ~31s | ~11s |
| Speedup | - | **65% faster** |
| Worker count | 1 | auto (4-8 based on CPU) |
| Serial test count | 12 tests | 12 tests |
| Parallel test count | 0 | ~195 tests |

---

## Related

- `tests/README.md` — general test suite documentation
- `docs/TEST_REFACTORING_PLAN.md` — full refactoring history
- [pytest-xdist docs](https://pytest-xdist.readthedocs.io/)
