"""
Pytest configuration for kurs-bot tests.
Sets up test environment and cleans up after test session.
Database URL is set by run_tests.ps1 before pytest is invoked.
"""
import os
from pathlib import Path
import pytest

TEST_DB_PATH = Path('src/data/test.db')

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """
    Setup test environment and cleanup after tests.
    - Removes old test database before tests start
    - Removes test database after tests complete
    """
    # Remove old test database if it exists
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
        print("\n🧪 Cleaned up old test database")
    
    print(f"🧪 Test database path: {TEST_DB_PATH}")
    
    yield
    
    # Cleanup after all tests
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
        print("\n✅ Test session complete - cleaned up test database")
    else:
        print("\n✅ Test session complete")
