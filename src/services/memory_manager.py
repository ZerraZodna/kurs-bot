import hashlib
import uuid
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from src.models.database import SessionLocal, Memory, init_db


class MemoryManager:
    def __init__(self, db: Optional[Session] = None):
        self.db = db or SessionLocal()

    def _hash_value(self, value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    def get_memory(self, user_id: int, key: str) -> List[Dict]:
        now = datetime.now(timezone.utc)
        q = self.db.query(Memory).filter(
            Memory.user_id == user_id,
            Memory.key == key,
            Memory.is_active == True,
        )
        rows = q.all()
        results = []
        for r in rows:
            if r.ttl_expires_at:
                ttl = r.ttl_expires_at
                if ttl.tzinfo is None:
                    # assume UTC if naive
                    ttl = ttl.replace(tzinfo=timezone.utc)
                if ttl < now:
                    # skip expired
                    continue
            results.append({
                "memory_id": r.memory_id,
                "key": r.key,
                "value": r.value,
                "confidence": r.confidence,
                "source": r.source,
                "created_at": r.created_at,
            })
        return results

    def store_memory(self, user_id: int, key: str, value: str, confidence: float = 1.0,
                     source: str = "dialogue_engine", ttl_hours: Optional[int] = None) -> int:
        """Store a memory with simple conflict resolution.

        Rules:
        - If an active memory exists with identical value_hash -> merge (update confidence/updated_at).
        - If active memory exists with different value_hash -> archive existing, insert new as active and set conflict_group_id.
        - If none exists -> insert new.
        """
        now = datetime.now(timezone.utc)
        value_hash = self._hash_value(value)
        ttl = None
        if ttl_hours:
            ttl = now + timedelta(hours=ttl_hours)

        # ensure tables exist
        init_db()

        # fetch active entries for same user/key
        existing = self.db.query(Memory).filter(
            Memory.user_id == user_id,
            Memory.key == key,
            Memory.is_active == True,
        ).all()

        # identical value exists -> merge
        for e in existing:
            if e.value_hash == value_hash:
                e.confidence = max(e.confidence, int(confidence))
                e.updated_at = now
                if ttl:
                    e.ttl_expires_at = ttl
                self.db.add(e)
                self.db.commit()
                return e.memory_id

        if existing:
            # conflict: archive existing and insert new with conflict_group
            group_id = str(uuid.uuid4())
            for e in existing:
                e.is_active = False
                e.archived_at = now
                e.conflict_group_id = group_id
                self.db.add(e)
            new = Memory(
                user_id=user_id,
                key=key,
                value=value,
                value_hash=value_hash,
                confidence=int(confidence),
                source=source,
                is_active=True,
                conflict_group_id=group_id,
                ttl_expires_at=ttl,
            )
            self.db.add(new)
            self.db.commit()
            return new.memory_id

        # no existing -> insert
        new = Memory(
            user_id=user_id,
            key=key,
            value=value,
            value_hash=value_hash,
            confidence=int(confidence),
            source=source,
            is_active=True,
            ttl_expires_at=ttl,
        )
        self.db.add(new)
        self.db.commit()
        return new.memory_id

    def purge_expired(self, days_keep: int = 365) -> int:
        """Delete archived rows older than days_keep. Returns number deleted."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days_keep)
        q = self.db.query(Memory).filter(
            Memory.is_active == False,
            Memory.archived_at != None,
            Memory.archived_at < cutoff,
        )
        count = q.count()
        q.delete(synchronize_session=False)
        self.db.commit()
        return count


if __name__ == '__main__':
    # quick manual test
    init_db()
    mm = MemoryManager()
    uid = 1
    mid = mm.store_memory(uid, 'learning_goal', 'Complete ACIM 365 lessons', confidence=1.0)
    print('stored', mid)
    print(mm.get_memory(uid, 'learning_goal'))
