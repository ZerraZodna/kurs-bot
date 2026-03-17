"""Unit tests for Memory model.

Migrated from tests/test_memory_model.py to use new test fixtures.
"""

import datetime

from sqlalchemy.orm import Session

from src.models.database import Memory, User


class TestMemoryModel:
    """Memory model unit tests using new fixtures."""

    def test_memory_crud(self, db_session: Session, test_user: User):
        """Should support Create, Read, Update, Delete operations."""
        # Given: A user exists in the database
        # When: Creating a new memory
        mem = Memory(
            user_id=test_user.user_id,
            category="fact",
            key="fav_color",
            value="blue",
            is_active=True,
            created_at=datetime.datetime.utcnow(),
            updated_at=datetime.datetime.utcnow()
        )
        db_session.add(mem)
        db_session.commit()
        
        # Then: Memory should be stored and have an ID
        assert mem.memory_id is not None

    def test_memory_read(self, db_session: Session, test_user: User):
        """Should be able to read stored memory."""
        # Given: A stored memory
        mem = Memory(
            user_id=test_user.user_id,
            category="fact",
            key="fav_color",
            value="blue",
            is_active=True,
            created_at=datetime.datetime.utcnow(),
            updated_at=datetime.datetime.utcnow()
        )
        db_session.add(mem)
        db_session.commit()
        
        # When: Reading the memory by key
        fetched = db_session.query(Memory).filter_by(key="fav_color").first()
        
        # Then: Should return the correct value
        assert fetched.value == "blue"

    def test_memory_update(self, db_session: Session, test_user: User):
        """Should be able to update stored memory."""
        # Given: A stored memory
        mem = Memory(
            user_id=test_user.user_id,
            category="fact",
            key="fav_color",
            value="blue",
            is_active=True,
            created_at=datetime.datetime.utcnow(),
            updated_at=datetime.datetime.utcnow()
        )
        db_session.add(mem)
        db_session.commit()
        
        # When: Updating the memory value
        fetched = db_session.query(Memory).filter_by(key="fav_color").first()
        fetched.value = "green"
        db_session.commit()
        
        # Then: Should reflect the new value
        updated = db_session.query(Memory).filter_by(memory_id=mem.memory_id).first()
        assert updated.value == "green"

    def test_memory_delete(self, db_session: Session, test_user: User):
        """Should be able to delete stored memory."""
        # Given: A stored memory
        mem = Memory(
            user_id=test_user.user_id,
            category="fact",
            key="fav_color",
            value="blue",
            is_active=True,
            created_at=datetime.datetime.utcnow(),
            updated_at=datetime.datetime.utcnow()
        )
        db_session.add(mem)
        db_session.commit()
        
        # When: Deleting the memory
        fetched = db_session.query(Memory).filter_by(key="fav_color").first()
        db_session.delete(fetched)
        db_session.commit()
        
        # Then: Memory should no longer exist
        assert db_session.query(Memory).filter_by(memory_id=mem.memory_id).first() is None

