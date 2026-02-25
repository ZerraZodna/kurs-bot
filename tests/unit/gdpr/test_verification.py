"""
Migrated tests for GDPR verification.
 migrated from tests/test_gdpr_verification.py
"""
import datetime

import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from src.models.database import Base, User
from src.services.gdpr_verification import create_verification, verify_code


@pytest.fixture(scope="function")
def db_session():
    """Create an in-memory database session for testing."""
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()


def _create_user(session):
    """Helper to create a test user."""
    user = User(
        external_id="gdpr-verify-1",
        channel="telegram",
        first_name="Test",
        last_name="User",
        email="test@example.com",
        phone_number="+4712345678",
        opted_in=True,
        created_at=datetime.datetime.utcnow(),
    )
    session.add(user)
    session.commit()
    return user


def test_gdpr_verification_flow(db_session):
    """Given: A user requests GDPR data export
    When: Creating and verifying a verification code
    Then: The verification flow works correctly
    """
    # Given: User exists
    user = _create_user(db_session)
    
    # When: Creating a verification code
    code = create_verification(
        session=db_session,
        user_id=user.user_id,
        channel="telegram",
        request_type="export",
        payload=None,
    )
    assert code.isdigit()

    # Then: Verification succeeds
    verification = verify_code(db_session, user.user_id, code)
    assert verification.verified_at is not None

