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
