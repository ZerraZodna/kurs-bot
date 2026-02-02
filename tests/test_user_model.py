import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.database import Base, User
import datetime

@pytest.fixture(scope="function")
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    yield session
    session.close()

def test_user_crud(db_session):
    # Create
    user = User(
        external_id="12345",
        channel="telegram",
        first_name="Test",
        last_name="User",
        opted_in=True,
        created_at=datetime.datetime.utcnow()
    )
    db_session.add(user)
    db_session.commit()
    assert user.user_id is not None

    # Read
    fetched = db_session.query(User).filter_by(external_id="12345").first()
    assert fetched is not None
    assert fetched.first_name == "Test"

    # Update
    fetched.first_name = "Updated"
    db_session.commit()
    updated = db_session.query(User).filter_by(user_id=user.user_id).first()
    assert updated.first_name == "Updated"

    # Delete
    db_session.delete(updated)
    db_session.commit()
    assert db_session.query(User).filter_by(user_id=user.user_id).first() is None
