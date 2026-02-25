"""Database fixtures for test isolation and setup.

Uses the application's own engine and SessionLocal (file-based test.db when
IS_TEST_ENV=1) so that data committed in db_session is visible to services
like TriggerMatcher and SchedulerService that also call SessionLocal()
internally.

Test isolation is provided by the ensure_test_db autouse fixture in
tests/conftest.py, which drops and recreates all tables before each test.
"""

import datetime
from typing import Generator

import pytest
from sqlalchemy.orm import Session

from src.models.database import Base, User, engine as _app_engine, SessionLocal


# Constants for test database
DEFAULT_TEST_USER_EXTERNAL_ID = "test_user_001"
DEFAULT_TEST_USER_FIRST_NAME = "Test"
DEFAULT_TEST_USER_CHANNEL = "telegram"


@pytest.fixture(scope="session")
def db_engine() -> Generator:
    """Session-scoped database engine.

    Returns the application engine so tests and services share the same DB.
    """
    yield _app_engine


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """Function-scoped database session.

    Uses the application's SessionLocal so that data committed here is
    visible to services (TriggerMatcher, SchedulerService, etc.) that
    also use SessionLocal() internally.

    Isolation is provided by the ensure_test_db autouse fixture in
    tests/conftest.py which drops and recreates all tables before each test.
    """
    session = SessionLocal()
    try:
        yield session
    finally:
        try:
            session.rollback()
        except Exception:
            pass
        session.close()


@pytest.fixture(scope="function")
def db_session_with_user(db_session) -> Generator[Session, None, None]:
    """Database session with a default test user pre-created.

    Use this when you need a user to exist for foreign key constraints.
    The user is available via db_session.query(User).first().
    """
    user = User(
        external_id=DEFAULT_TEST_USER_EXTERNAL_ID,
        channel=DEFAULT_TEST_USER_CHANNEL,
        first_name=DEFAULT_TEST_USER_FIRST_NAME,
        last_name="User",
        opted_in=True,
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add(user)
    db_session.commit()

    yield db_session


@pytest.fixture(scope="function")
def clean_db() -> Generator[None, None, None]:
    """Ensures database is clean before test runs.

    Drops and recreates all tables for a completely fresh state.
    Use sparingly as it's slower than the default per-test isolation.
    """
    Base.metadata.drop_all(_app_engine)
    Base.metadata.create_all(_app_engine)
    yield
