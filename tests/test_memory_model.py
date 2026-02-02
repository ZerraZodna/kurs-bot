import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.database import Base, Memory, User
import datetime

@pytest.fixture(scope="function")
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    # Add a user for FK
    user = User(external_id="54321", channel="telegram", first_name="Mem", last_name="Test", opted_in=True, created_at=datetime.datetime.utcnow())
    session.add(user)
    session.commit()
    yield session
    session.close()

def test_memory_crud(db_session):
    user = db_session.query(User).first()
    # Create
    mem = Memory(
        user_id=user.user_id,
        category="fact",
        key="fav_color",
        value="blue",
        confidence=0.9,
        is_active=True,
        created_at=datetime.datetime.utcnow(),
        updated_at=datetime.datetime.utcnow()
    )
    db_session.add(mem)
    db_session.commit()
    assert mem.memory_id is not None

    # Read
    fetched = db_session.query(Memory).filter_by(key="fav_color").first()
    assert fetched.value == "blue"

    # Update
    fetched.value = "green"
    db_session.commit()
    updated = db_session.query(Memory).filter_by(memory_id=mem.memory_id).first()
    assert updated.value == "green"

    # Delete
    db_session.delete(updated)
    db_session.commit()
    assert db_session.query(Memory).filter_by(memory_id=mem.memory_id).first() is None
