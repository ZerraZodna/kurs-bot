"""
Pytest configuration for kurs-bot tests.
Ensures tests always use a separate test database.
"""
import os
import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

# Force tests to use a separate test database
os.environ['DATABASE_URL'] = 'sqlite:///./src/data/test.db'

@pytest.fixture(scope="session", autouse=True)
def setup_test_environment():
    """Ensure test database is used for all tests."""
    # This runs before any tests
    print("\n🧪 Using test database: test.db")
    yield
    # Cleanup after all tests
    print("\n✅ Test session complete")
