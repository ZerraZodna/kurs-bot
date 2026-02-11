import pytest

# Ensure test database is initialized for every test to guarantee isolation.
# This autouse fixture runs before each test and calls `init_db()`.
from src.models.database import init_db, engine, Base


@pytest.fixture(autouse=True)
def ensure_test_db():
    """Reset the test database before each test to ensure isolation.

    This drops all tables and recreates them so primary keys and data do
    not persist across tests.
    """
    # Drop and recreate all tables to ensure a clean slate for each test
    Base.metadata.drop_all(bind=engine)
    Base.metadata.create_all(bind=engine)
    yield
