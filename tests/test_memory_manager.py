import pytest
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker
from src.models.database import Base, User, Memory
from src.services.memory_manager import MemoryManager
from src.services.maintenance import purge_archived_memories
import datetime

@pytest.fixture(scope="function")
def db_session():
    engine = create_engine("sqlite:///:memory:")
    Base.metadata.create_all(engine)
    Session = sessionmaker(bind=engine)
    session = Session()
    # Add a user for FK
    user = User(external_id="99999", channel="telegram", first_name="Test", last_name="User", opted_in=True, created_at=datetime.datetime.utcnow())
    session.add(user)
    session.commit()
    yield session
    session.close()

def test_store_and_get_memory(db_session):
    mm = MemoryManager(db=db_session)
    user = db_session.query(User).first()
    # Store memory
    mem_id = mm.store_memory(user.user_id, "goal", "Learn Python", confidence=0.8, category="fact")
    assert mem_id is not None
    # Get memory
    memories = mm.get_memory(user.user_id, "goal")
    assert len(memories) == 1
    assert memories[0]["value"] == "Learn Python"

def test_store_memory_conflict(db_session):
    mm = MemoryManager(db=db_session)
    user = db_session.query(User).first()
    # Store initial memory
    mem_id1 = mm.store_memory(user.user_id, "goal", "Learn Python", confidence=0.8, category="fact")
    # Store conflicting memory (different value)
    mem_id2 = mm.store_memory(user.user_id, "goal", "Learn SQL", confidence=0.9, category="fact")
    assert mem_id1 != mem_id2
    # Only one active memory should exist
    active = db_session.query(Memory).filter_by(user_id=user.user_id, key="goal", is_active=True).all()
    assert len(active) == 1
    # Archived memory should exist
    archived = db_session.query(Memory).filter_by(user_id=user.user_id, key="goal", is_active=False).all()
    assert len(archived) == 1

def test_store_memory_merge(db_session):
    mm = MemoryManager(db=db_session)
    user = db_session.query(User).first()
    # Store memory
    mem_id1 = mm.store_memory(user.user_id, "goal", "Learn Python", confidence=0.8, category="fact")
    # Store again with same value (should merge)
    mem_id2 = mm.store_memory(user.user_id, "goal", "Learn Python", confidence=0.9, category="fact")
    assert mem_id1 == mem_id2
    mem = db_session.query(Memory).filter_by(memory_id=mem_id1).first()
    assert mem.confidence == 0.9 or mem.confidence == 1  # int(confidence)

def test_purge_expired(db_session):
    mm = MemoryManager(db=db_session)
    user = db_session.query(User).first()
    # Add archived memory older than 2 years
    old_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=800)
    mem = Memory(
        user_id=user.user_id,
        category="fact",
        key="old_key",
        value="old_value",
        confidence=1.0,
        is_active=False,
        archived_at=old_date,
        created_at=old_date,
        updated_at=old_date
    )
    db_session.add(mem)
    db_session.commit()
    purged = purge_archived_memories(days_keep=365, session=db_session)
    assert purged == 1
    # Should be deleted
    assert db_session.query(Memory).filter_by(key="old_key").count() == 0
