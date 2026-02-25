"""Unit tests for MemoryManager.

Refactored to use new test fixtures from tests/fixtures/
"""

import datetime

import pytest
from sqlalchemy.orm import Session

from src.models.database import Memory
from src.memories import MemoryManager
from src.services.maintenance import purge_archived_memories
from tests.utils.assertions import assert_memory_stored


class TestMemoryManager:
    """Memory manager unit tests using new fixtures."""

    def test_store_and_get_memory(self, db_session: Session, test_user):
        """Should store and retrieve memory correctly."""
        # Given: A memory manager
        mm = MemoryManager(db=db_session)
        
        # When: Storing a memory
        mem_id = mm.store_memory(
            test_user.user_id, "goal", "Learn Python", 
            confidence=0.8, category="fact"
        )
        
        # Then: Memory should be stored and retrievable
        assert mem_id is not None
        memories = mm.get_memory(test_user.user_id, "goal")
        assert len(memories) == 1
        assert memories[0]["value"] == "Learn Python"

    def test_store_memory_conflict(self, db_session: Session, test_user):
        """Different value should archive old memory."""
        # Given: A memory manager
        mm = MemoryManager(db=db_session)
        
        # When: Storing initial memory then conflicting one
        mem_id1 = mm.store_memory(
            test_user.user_id, "goal", "Learn Python", 
            confidence=0.8, category="fact"
        )
        mem_id2 = mm.store_memory(
            test_user.user_id, "goal", "Learn SQL", 
            confidence=0.9, category="fact"
        )
        
        # Then: Should create new memory, archive old one
        assert mem_id1 != mem_id2
        
        # Only one active memory
        active = db_session.query(Memory).filter_by(
            user_id=test_user.user_id, key="goal", is_active=True
        ).all()
        assert len(active) == 1
        
        # Archived memory should exist
        archived = db_session.query(Memory).filter_by(
            user_id=test_user.user_id, key="goal", is_active=False
        ).all()
        assert len(archived) == 1

    def test_store_memory_merge(self, db_session: Session, test_user):
        """Same value should merge (update confidence)."""
        # Given: A memory manager
        mm = MemoryManager(db=db_session)
        
        # When: Storing same value twice
        mem_id1 = mm.store_memory(
            test_user.user_id, "goal", "Learn Python", 
            confidence=0.8, category="fact"
        )
        mem_id2 = mm.store_memory(
            test_user.user_id, "goal", "Learn Python", 
            confidence=0.9, category="fact"
        )
        
        # Then: Should merge (same ID, updated confidence)
        assert mem_id1 == mem_id2
        mem = db_session.query(Memory).filter_by(memory_id=mem_id1).first()
        assert mem.confidence in (0.9, 1.0)  # Merged confidence

    def test_purge_expired(self, db_session: Session, test_user):
        """Old archived memories should be purged."""
        # Given: An old archived memory
        old_date = datetime.datetime.now(datetime.timezone.utc) - datetime.timedelta(days=800)
        mem = Memory(
            user_id=test_user.user_id,
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
        
        # When: Purging old memories
        purged = purge_archived_memories(days_keep=365, session=db_session)
        
        # Then: Old memory should be deleted
        assert purged == 1
        assert db_session.query(Memory).filter_by(key="old_key").count() == 0

