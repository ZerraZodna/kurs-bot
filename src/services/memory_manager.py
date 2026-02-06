import hashlib
import uuid
import asyncio
import logging
from datetime import datetime, timezone, timedelta
from typing import Optional, List, Dict
from sqlalchemy.orm import Session
from src.models.database import SessionLocal, Memory, init_db
from src.services.embedding_service import get_embedding_service

logger = logging.getLogger(__name__)


class MemoryManager:
    def __init__(self, db: Optional[Session] = None):
        self.db = db or SessionLocal()
        self.embedding_service = get_embedding_service()

    def _hash_value(self, value: str) -> str:
        return hashlib.sha256(value.encode("utf-8")).hexdigest()

    async def _generate_and_store_embedding(self, memory_id: int, value: str):
        """
        Generate embedding for a memory and store it
        
        Args:
            memory_id: ID of the memory to generate embedding for
            value: Memory value to generate embedding from
        """
        try:
            embedding = await self.embedding_service.generate_embedding(value)
            if embedding:
                # Create a new session for this async task
                db = SessionLocal()
                try:
                    memory = db.query(Memory).filter(Memory.memory_id == memory_id).first()
                    if memory:
                        memory.embedding = self.embedding_service.embedding_to_bytes(embedding)
                        memory.embedding_version = 1
                        memory.embedding_generated_at = datetime.now(timezone.utc)
                        db.add(memory)
                        db.commit()
                        logger.debug(f"Generated embedding for memory {memory_id}")
                    else:
                        logger.warning(f"Memory {memory_id} not found for embedding generation")
                finally:
                    db.close()
            else:
                logger.warning(f"Failed to generate embedding for memory {memory_id}")
        except Exception as e:
            logger.error(f"Error generating embedding for memory {memory_id}: {e}")

    def _schedule_embedding_generation(self, memory_id: int, value: str):
        """Schedule embedding generation safely.

        If an asyncio event loop is running, schedule as a background task.
        Otherwise run the coroutine synchronously so it is awaited.
        """
        try:
            loop = asyncio.get_running_loop()
            loop.create_task(self._generate_and_store_embedding(memory_id, value))
        except RuntimeError:
            # No running loop (e.g. tests or simple script) — run synchronously
            try:
                asyncio.run(self._generate_and_store_embedding(memory_id, value))
            except Exception as ex:
                logger.warning(f"Could not run embedding generation synchronously: {ex}")
        except Exception as ex:
            logger.warning(f"Could not schedule embedding generation: {ex}")

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
                     source: str = "dialogue_engine", ttl_hours: Optional[int] = None, category: str = "fact",
                     allow_duplicates: bool = False, generate_embedding: bool = True) -> int:
        """Store a memory with simple conflict resolution.

        Rules (when allow_duplicates=False):
        - If an active memory exists with identical value_hash -> merge (update confidence/updated_at).
        - If active memory exists with different value_hash -> archive existing, insert new as active and set conflict_group_id.
        - If none exists -> insert new.
        
        When allow_duplicates=True:
        - Always insert new memory without archiving existing ones
        
        Args:
            user_id: User ID
            key: Memory key
            value: Memory value
            confidence: Confidence score (0.0-1.0)
            source: Source of memory
            ttl_hours: Hours until memory expires (None = never)
            category: Memory category
            allow_duplicates: Allow duplicate values
            generate_embedding: Generate embedding for semantic search (runs async)
        
        Returns:
            Memory ID of stored memory
        """
        now = datetime.now(timezone.utc)
        value_hash = self._hash_value(value)
        ttl = None
        if ttl_hours:
            ttl = now + timedelta(hours=ttl_hours)

        # ensure tables exist
        init_db()

        # fetch active entries for same user/key/category
        existing = self.db.query(Memory).filter(
            Memory.user_id == user_id,
            Memory.key == key,
            Memory.category == category,
            Memory.is_active == True,
        ).all()

        # identical value exists -> merge
        for e in existing:
            if e.value_hash == value_hash:
                e.confidence = max(e.confidence, float(confidence))
                e.updated_at = now
                if ttl:
                    e.ttl_expires_at = ttl
                self.db.add(e)
                self.db.commit()
                
                # Generate embedding if needed
                if generate_embedding:
                    self._schedule_embedding_generation(e.memory_id, e.value)
                
                return e.memory_id

        # If allow_duplicates, just insert new memory
        if allow_duplicates:
            new = Memory(
                user_id=user_id,
                category=category,
                key=key,
                value=value,
                value_hash=value_hash,
                confidence=float(confidence),
                source=source,
                is_active=True,
                ttl_expires_at=ttl,
            )
            self.db.add(new)
            self.db.commit()
            
            # Generate embedding if needed
            if generate_embedding:
                self._schedule_embedding_generation(new.memory_id, new.value)
            
            return new.memory_id

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
                category=category,
                key=key,
                value=value,
                value_hash=value_hash,
                confidence=float(confidence),
                source=source,
                is_active=True,
                conflict_group_id=group_id,
                ttl_expires_at=ttl,
            )
            self.db.add(new)
            self.db.commit()
            
            # Generate embedding if needed
            if generate_embedding:
                self._schedule_embedding_generation(new.memory_id, new.value)
            
            return new.memory_id

        # no existing -> insert
        new = Memory(
            user_id=user_id,
            category=category,
            key=key,
            value=value,
            value_hash=value_hash,
            confidence=float(confidence),
            source=source,
            is_active=True,
            ttl_expires_at=ttl,
        )
        self.db.add(new)
        self.db.commit()
        
        # Generate embedding if needed
        if generate_embedding:
            self._schedule_embedding_generation(new.memory_id, new.value)
        
        return new.memory_id

    def archive_memories(self, user_id: int, memory_ids: List[int]) -> int:
        """Archive (soft-delete) memories by IDs for a user. Returns count archived."""
        if not memory_ids:
            return 0
        now = datetime.now(timezone.utc)
        q = self.db.query(Memory).filter(
            Memory.user_id == user_id,
            Memory.memory_id.in_(memory_ids),
            Memory.is_active == True,
        )
        updated = q.update(
            {Memory.is_active: False, Memory.archived_at: now},
            synchronize_session=False,
        )
        self.db.commit()
        return updated

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
