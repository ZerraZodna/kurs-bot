"""
Pytest configuration for kurs-bot tests.
Ensures tests always use a separate test database.
"""
import os
import shutil
from pathlib import Path
import pytest

# Force tests to use a separate test database
TEST_DB_URL = 'sqlite:///./src/data/test.db'
os.environ['DATABASE_URL'] = TEST_DB_URL

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """
    Ensure test database is used for all tests.
    Cleans up test database after test session completes.
    """
    test_db_path = Path('src/data/test.db')
    
    # Remove old test database if it exists
    if test_db_path.exists():
        test_db_path.unlink()
        print("\n🧪 Cleaned up old test database")
    
    print(f"🧪 Using test database: {TEST_DB_URL}")
    
    yield
    
    # Cleanup after all tests
    if test_db_path.exists():
        test_db_path.unlink()
        print("\n✅ Test session complete - cleaned up test database")
    else:
        print("\n✅ Test session complete")
