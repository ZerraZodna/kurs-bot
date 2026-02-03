"""
Pytest configuration for kurs-bot tests.
Central location for all test database setup and configuration.
"""
import os
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
    - Removes test database after tests complete
    """
    # Remove old test database if it exists
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
        print("\n🧪 Cleaned up old test database")
    
    print(f"🧪 Using test database: {TEST_DB_URL}")
    
    yield
    
    # Cleanup after all tests
    if TEST_DB_PATH.exists():
        TEST_DB_PATH.unlink()
        print("\n✅ Test session complete - cleaned up test database")
    else:
        print("\n✅ Test session complete")
