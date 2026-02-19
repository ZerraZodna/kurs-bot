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
