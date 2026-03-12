import logging
from typing import Optional, List
from sqlalchemy.orm import Session
from src.models.database import SessionLocal
from src.memories.store import MemoryStore
from src.memories.memory_handler import MemoryHandler, MemoryRecord
from src.memories.constants import MemoryCategory, MemoryKey

logger = logging.getLogger(__name__)


class MemoryManager:
    def __init__(self, db: Optional[Session] = None, memory_store: Optional[MemoryStore] = None):
        self.db = db or SessionLocal()
        self.memory_handler: MemoryStore = memory_store or MemoryHandler(self.db)
        # Lazy initialization of topic_manager
        self._topic_manager = None

    # Note: embedding generation scheduling and persistence removed.
    # The private helpers that generated and stored embeddings were deleted
    # to avoid persisting per-memory embedding bytes.

    def get_memory(self, user_id: int, key: str) -> List[MemoryRecord]:
        return self.memory_handler.get_memory(user_id=user_id, key=key)

    def store_memory(self, user_id: int, key: str, value: str,
                     source: str = "dialogue_engine", ttl_hours: Optional[int] = None, category: str = "fact",
                     allow_duplicates: bool = False) -> int:
        """Store a memory with simple conflict resolution.

        Rules (when allow_duplicates=False):
        - If an active memory exists with identical value_hash -> merge (update updated_at).
        - If active memory exists with different value_hash -> archive existing, insert new as active and set conflict_group_id.
        - If none exists -> insert new.
        
        When allow_duplicates=True:
        - Always insert new memory without archiving existing ones
        
        Args:
            user_id: User ID
            key: Memory key
            value: Memory value
            source: Source of memory
            ttl_hours: Hours until memory expires (None = never)
            category: Memory category
            allow_duplicates: Allow duplicate values
        Returns:
            Memory ID of stored memory
        """
        memory_id = self.memory_handler.store_memory(
            user_id=user_id,
            key=key,
            value=value,
            source=source,
            ttl_hours=ttl_hours,
            category=category,
            allow_duplicates=allow_duplicates,
        )
        
        # Generate embedding if needed — removed in this branch.
        # If this memory indicates a preferred lesson time, do NOT modify schedules here.
        # Creating schedules is the responsibility of the schedule/triggering codepath
        # (e.g. FunctionExecutor) to avoid unexpected side-effects from memory writes.
        if key == MemoryKey.PREFERRED_LESSON_TIME:
            logger.info(f"Stored preferred_lesson_time for user {user_id} (no auto-schedule created)")

        return memory_id


    def archive_memories(self, user_id: int, memory_ids: List[int]) -> int:
        """Archive (soft-delete) memories by IDs for a user. Returns count archived."""
        return self.memory_handler.archive_memories(user_id=user_id, memory_ids=memory_ids)

    @property
    def topic_manager(self):
        """Lazy initialization of TopicManager for topic-based memory access."""
        if self._topic_manager is None:
            from src.memories.topic_manager import TopicManager
            self._topic_manager = TopicManager(self)
        return self._topic_manager

if __name__ == '__main__':
    # quick manual test
    from src.models.database import init_db
    init_db()
    mm = MemoryManager()
    uid = 1
    mid = mm.store_memory(uid, 'learning_goal', 'Complete ACIM 365 lessons')
    print('stored', mid)
    print(mm.get_memory(uid, 'learning_goal'))
