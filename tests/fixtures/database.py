"""Database fixtures for test isolation and setup."""

import datetime
from typing import Generator

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.orm import sessionmaker, Session

from src.models.database import Base, User


# Constants for test database
TEST_DB_URL = "sqlite:///:memory:"
DEFAULT_TEST_USER_EXTERNAL_ID = "test_user_001"
DEFAULT_TEST_USER_FIRST_NAME = "Test"
DEFAULT_TEST_USER_CHANNEL = "telegram"


@pytest.fixture(scope="session")
def db_engine() -> Generator:
    """Session-scoped database engine.
    
    Creates a single engine for the entire test session.
    All tests share this engine but use separate connections/transactions.
    """
    engine = create_engine(TEST_DB_URL, connect_args={"check_same_thread": False})
    
    # Create all tables once at session start
    Base.metadata.create_all(engine)
    
    yield engine
    
    # Cleanup at session end
    Base.metadata.drop_all(engine)
    engine.dispose()


@pytest.fixture(scope="function")
def db_connection(db_engine) -> Generator:
    """Function-scoped database connection with transaction.
    
    Provides a connection that rolls back after each test,
    ensuring complete test isolation.
    """
    connection = db_engine.connect()
    transaction = connection.begin()
    
    yield connection
    
    # Rollback all changes and close connection
    transaction.rollback()
    connection.close()


@pytest.fixture(scope="function")
def db_session(db_connection) -> Generator[Session, None, None]:
    """Function-scoped database session with automatic rollback.
    
    This is the primary fixture for database access in tests.
    All changes are rolled back after each test for isolation.
    """
    # Create session bound to the connection
    session_factory = sessionmaker(bind=db_connection)
    session = session_factory()
    
    # Enable foreign key constraints for SQLite
    db_connection.execute(text("PRAGMA foreign_keys=ON"))
    
    yield session
    
    # Close session (changes already rolled back by db_connection)
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
    
    # User is automatically cleaned up by transaction rollback


@pytest.fixture(scope="function")
def clean_db(db_engine) -> Generator[None, None, None]:
    """Ensures database is clean before test runs.
    
    Drops and recreates all tables for a completely fresh state.
    Use sparingly as it's slower than transaction rollback.
    """
    Base.metadata.drop_all(db_engine)
    Base.metadata.create_all(db_engine)
    yield
    # No cleanup needed - next test will recreate if needed
