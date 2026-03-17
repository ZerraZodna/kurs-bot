"""Centralized SQL/data-access helpers for memory records.

This module contains the low-level DB logic for reading/writing `Memory` rows.
Higher-level orchestration (side-effects, domain decisions) stays in manager
or service modules.
"""

from __future__ import annotations

import hashlib
import logging
import uuid
from datetime import datetime, timedelta
from typing import List, Optional

from sqlalchemy.orm import Session

from src.core.timezone import utc_now
from src.memories.store import MemoryStore
from src.models.database import Memory, init_db

from .types import MemoryEntity, MemoryRecord

logger = logging.getLogger(__name__)


class MemoryHandler(MemoryStore):
    """DB-focused operations for memory persistence."""

    def __init__(self, db: Session):
        self.db = db

    @staticmethod
    def hash_value(value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    @staticmethod
    def build_active_query(session: Session, user_id: int, categories: Optional[List[str]] = None):
        """Build a base query for active user memories."""
        q = session.query(Memory).filter(Memory.user_id == user_id).filter(Memory.is_active == True)
        if categories:
            q = q.filter(Memory.category.in_(categories))
        return q

    def list_active_by_key(self, user_id: int, key: str) -> List[MemoryEntity]:
        return (
            self.db.query(Memory).filter(Memory.user_id == user_id, Memory.key == key, Memory.is_active == True).all()
        )

    def list_active_memories(
        self,
        user_id: int,
        categories: Optional[List[str]] = None,
        order_ascending: bool = False,
    ) -> List[MemoryEntity]:
        q = self.build_active_query(session=self.db, user_id=user_id, categories=categories)
        if order_ascending:
            q = q.order_by(Memory.created_at.asc())
        return q.all()

    def keyword_candidates(
        self,
        user_id: int,
        query_text: str,
        categories: Optional[List[str]] = None,
        limit: Optional[int] = None,
    ) -> List[MemoryEntity]:
        like_pattern = f"%{query_text.strip()}%"
        rows = (
            self
            .build_active_query(session=self.db, user_id=user_id, categories=categories)
            .filter(Memory.value.ilike(like_pattern))
            .all()
        )
        if limit is not None:
            rows = rows[:limit]
        return rows

    def top_active_memories(
        self,
        user_id: int,
        categories: Optional[List[str]] = None,
        limit: int = 100,
    ) -> List[MemoryEntity]:
        rows = self.list_active_memories(user_id=user_id, categories=categories)
        return rows[:limit]

    def list_user_memories(self, user_id: int) -> List[MemoryEntity]:
        return self.db.query(Memory).filter(Memory.user_id == user_id).all()

    def get_user_memory_by_id(self, user_id: int, memory_id: int) -> Optional[MemoryEntity]:
        return self.db.query(Memory).filter(Memory.memory_id == memory_id, Memory.user_id == user_id).first()

    @staticmethod
    def _is_expired(ttl_expires_at: Optional[datetime], now_utc: datetime) -> bool:
        if not ttl_expires_at:
            return False
        ttl = ttl_expires_at
        if ttl.tzinfo is None:
            # Lazy import to avoid import cycles with timezone utilities.
            from src.core.timezone import to_utc

            ttl = to_utc(ttl)
        return ttl < now_utc

    @staticmethod
    def _to_public_dict(row: MemoryEntity) -> MemoryRecord:
        return {
            "memory_id": row.memory_id,
            "key": row.key,
            "value": row.value,
            "source": row.source,
            "created_at": row.created_at,
        }

    def get_memory(self, user_id: int, key: str) -> List[MemoryRecord]:
        """Fetch active, non-expired memories for a key."""
        now = utc_now()
        rows = self.list_active_by_key(user_id=user_id, key=key)
        return [self._to_public_dict(row) for row in rows if not self._is_expired(row.ttl_expires_at, now)]

    def store_memory(
        self,
        user_id: int,
        key: str,
        value: str,
        source: str = "dialogue_engine",
        ttl_hours: Optional[int] = None,
        category: str = "fact",
        allow_duplicates: bool = False,
    ) -> int:
        """Store a memory row with conflict handling and return memory_id."""
        # Validate and normalize category for consistency
        from src.memories.constants import MemoryCategory

        validated_category = MemoryCategory.normalize(category)
        if validated_category != category:
            logger.debug(f"Category '{category}' normalized to '{validated_category}' for key '{key}'")
        category = validated_category

        now = utc_now()
        value_hash = self.hash_value(value)
        ttl = now + timedelta(hours=ttl_hours) if ttl_hours else None

        # Ensure tables exist for environments that initialize lazily.
        init_db()

        existing = (
            self.db
            .query(Memory)
            .filter(
                Memory.user_id == user_id,
                Memory.key == key,
                Memory.category == category,
                Memory.is_active == True,
            )
            .all()
        )

        # identical value -> merge
        for row in existing:
            if row.value_hash == value_hash:
                row.updated_at = now
                if ttl:
                    row.ttl_expires_at = ttl
                self.db.add(row)
                self.db.commit()
                return row.memory_id

        # if requested, always insert
        if allow_duplicates:
            created = Memory(
                user_id=user_id,
                category=category,
                key=key,
                value=value,
                value_hash=value_hash,
                source=source,
                is_active=True,
                ttl_expires_at=ttl,
            )
            self.db.add(created)
            self.db.commit()
            return created.memory_id

        # conflict -> archive previous active rows
        if existing:
            group_id = str(uuid.uuid4())
            for row in existing:
                row.is_active = False
                row.archived_at = now
                row.conflict_group_id = group_id
                self.db.add(row)
            created = Memory(
                user_id=user_id,
                category=category,
                key=key,
                value=value,
                value_hash=value_hash,
                source=source,
                is_active=True,
                conflict_group_id=group_id,
                ttl_expires_at=ttl,
            )
            self.db.add(created)
            self.db.commit()
            return created.memory_id

        # no previous value
        created = Memory(
            user_id=user_id,
            category=category,
            key=key,
            value=value,
            value_hash=value_hash,
            source=source,
            is_active=True,
            ttl_expires_at=ttl,
        )
        self.db.add(created)
        self.db.commit()
        return created.memory_id

    def archive_memories(self, user_id: int, memory_ids: List[int]) -> int:
        if not memory_ids:
            return 0
        now = utc_now()
        updated = (
            self.db
            .query(Memory)
            .filter(
                Memory.user_id == user_id,
                Memory.memory_id.in_(memory_ids),
                Memory.is_active == True,
            )
            .update({Memory.is_active: False, Memory.archived_at: now}, synchronize_session=False)
        )
        self.db.commit()
        return updated

    def delete_user_memories(self, user_id: int, commit: bool = False) -> int:
        """Hard-delete all memory rows for a user."""
        deleted = self.db.query(Memory).filter(Memory.user_id == user_id).delete(synchronize_session=False)
        if commit:
            self.db.commit()
        return int(deleted or 0)

    def delete_all_memories(self, commit: bool = False) -> int:
        deleted = self.db.query(Memory).delete(synchronize_session=False)
        if commit:
            self.db.commit()
        return int(deleted or 0)

    def purge_archived_before(self, cutoff: datetime) -> int:
        q = self.db.query(Memory).filter(
            Memory.is_active == False,
            Memory.archived_at != None,
            Memory.archived_at < cutoff,
        )
        deleted = q.count()
        q.delete(synchronize_session=False)
        self.db.commit()
        return int(deleted or 0)

    def purge_expired_ttl_before(self, cutoff: datetime) -> int:
        q = self.db.query(Memory).filter(
            Memory.ttl_expires_at != None,
            Memory.ttl_expires_at < cutoff,
        )
        deleted = q.count()
        q.delete(synchronize_session=False)
        self.db.commit()
        return int(deleted or 0)
