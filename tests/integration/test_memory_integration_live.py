"""
Migrated live integration tests for memory with real Ollama.
 migrated from tests/test_memory_integration_live.py
"""

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.database import Base, User


@pytest.fixture(scope="function")
def db_session():
    """Create an in-memory database session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    # Add a user for FK
    user = User(external_id="99997", channel="telegram", first_name="Live", last_name="User", opted_in=True)
    session.add(user)
    session.commit()
    yield session
    session.close()
