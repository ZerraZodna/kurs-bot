"""Database fixtures for test isolation and setup.

This is the single source of truth for test database configuration.
Uses temporary file-based SQLite databases per worker for parallel test safety.

The application engine is not used - instead we create a dedicated test engine
to ensure complete isolation from any production or development databases.

Test isolation provided by conftest.py truncate_test_tables per test + module create_all.

For parallel test execution with pytest-xdist, each worker gets its own
temporary database file to avoid SQLite file locking issues.
"""

import os
import datetime
from typing import Generator

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker

@pytest.fixture(scope="module", autouse=True)
def module_db_session(db_engine):
    """Module-scoped SessionLocal monkeypatch for test isolation."""
    from _pytest.monkeypatch import MonkeyPatch
    mp = MonkeyPatch()
    TestSessionLocal = sessionmaker(bind=db_engine, autoflush=False, autocommit=False, future=True)
    mp.setattr("src.models.database.SessionLocal", TestSessionLocal)

from src.models.database import Base
from src.models import User


# Constants for test database
DEFAULT_TEST_USER_EXTERNAL_ID = "test_user_001"
DEFAULT_TEST_USER_FIRST_NAME = "Test"
DEFAULT_TEST_USER_CHANNEL = "telegram"


@pytest.fixture(scope="session")
def db_engine(tmp_path_factory) -> Generator:
    """Session-scoped database engine with worker-aware isolation.

    When running with pytest-xdist, each worker gets its own temporary
    database file to avoid SQLite file locking issues.
    
    Always creates a temporary database, even for the main worker, to ensure
    test isolation and avoid issues with the application database.
    """
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
    
    # Schema creation moved to ensure_test_db fixture for per-test isolation
    
    yield engine
    
    engine.dispose()


@pytest.fixture(scope="function")
def db_session() -> Generator[Session, None, None]:
    """Function-scoped DB session (SessionLocal already module-patched for test DB). 

    Uses worker-specific engine via module monkeypatch.
    Isolation via conftest truncate_test_tables + module_db_setup."""
    from src.models.database import SessionLocal
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

