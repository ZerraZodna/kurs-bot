import logging
from typing import Optional, List
from sqlalchemy.orm import Session
from src.models.database import SessionLocal
from src.memories.store import MemoryStore
from src.memories.types import MemoryRecord
from src.memories.memory_handler import MemoryHandler
from src.memories.constants import MemoryCategory, MemoryKey

logger = logging.getLogger(__name__)


class MemoryManager:
    def __init__(self, db: Optional[Session] = None, memory_store: Optional[MemoryStore] = None):
        self.db = db or SessionLocal()
        self.memory_handler: MemoryStore = memory_store or MemoryHandler(self.db)
        # Lazy initialization of topic_manager
        self._topic_manager = None
        # Lazy initialization of AI judge
        self._ai_judge = None

    @property
    def ai_judge(self):
        """Lazy initialization of AI judge for memory quality/conflict detection."""
        if self._ai_judge is None:
            from src.memories.ai_judge import MemoryJudge
            self._ai_judge = MemoryJudge()
        return self._ai_judge

    # Note: embedding generation scheduling and persistence removed.
    # The private helpers that generated and stored embeddings were deleted
    # to avoid persisting per-memory embedding bytes.

    def get_memory(self, user_id: int, key: str) -> List[MemoryRecord]:
        return self.memory_handler.get_memory(user_id=user_id, key=key)

    def store_memory(self, user_id: int, key: str, value: str, confidence: float = 1.0,
                     source: str = "dialogue_engine", ttl_hours: Optional[int] = None, category: str = "fact",
                     allow_duplicates: bool = False) -> int:
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
        Returns:
            Memory ID of stored memory
        """
        memory_id = self.memory_handler.store_memory(
            user_id=user_id,
            key=key,
            value=value,
            confidence=confidence,
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

    async def store_memory_with_judgment(
        self,
        user_id: int,
        key: str,
        value: str,
        user_message: str,
        confidence: float = 1.0,
        source: str = "dialogue_engine",
        ttl_hours: Optional[int] = None,
        category: str = "fact",
        allow_duplicates: bool = False
    ) -> Optional[int]:
        """Store a memory with AI-powered quality check and conflict resolution.
        
        This method uses the AI judge to:
        1. Validate memory quality (detect corrupted values)
        2. Find semantic conflicts with existing memories
        3. Decide whether to store, clean, archive, or flag
        
        Args:
            user_id: User ID
            key: Memory key
            value: Memory value (may be cleaned by AI)
            user_message: Original user message for context
            confidence: Confidence score (0.0-1.0)
            source: Source of memory
            ttl_hours: Hours until memory expires (None = never)
            category: Memory category
            allow_duplicates: Bypass AI judgment if True
        
        Returns:
            Memory ID if stored, None if rejected by AI judge
        """
        if allow_duplicates:
            # Bypass AI judgment for explicit duplicates
            return self.store_memory(
                user_id=user_id,
                key=key,
                value=value,
                confidence=confidence,
                source=source,
                ttl_hours=ttl_hours,
                category=category,
                allow_duplicates=True
            )
        
        # Get all existing memories for context
        from src.models.database import Memory
        existing = (
            self.db.query(Memory)
            .filter(Memory.user_id == user_id, Memory.is_active == True)
            .all()
        )
        
        # AI evaluates the proposed memory
        decision = await self.ai_judge.evaluate_storage(
            user_id=user_id,
            proposed_key=key,
            proposed_value=value,
            user_message=user_message,
            existing_memories=existing
        )
        
        logger.info(f"AI Judge [{key}]: quality={decision.quality_score:.2f}, store={decision.should_store}")
        if decision.reasoning:
            logger.debug(f"AI Judge reasoning: {decision.reasoning}")
        
        # Reject low quality memories
        if not decision.should_store:
            logger.warning(f"AI Judge rejected {key}: {decision.issues}")
            return None
        
        # Use cleaned value if provided
        final_value = decision.cleaned_value if decision.cleaned_value else value
        
        # Handle conflicts
        for conflict in decision.conflicts:
            if conflict.action == "REPLACE":
                logger.info(f"AI Judge: Archiving memory {conflict.existing_memory_id} (replaced by new {key})")
                self.archive_memories(user_id, [conflict.existing_memory_id])
            elif conflict.action == "MERGE":
                # For now, just use the new value (could be enhanced to actually merge)
                logger.info(f"AI Judge: Merging with memory {conflict.existing_memory_id}")
            elif conflict.action == "FLAG":
                logger.warning(f"AI Judge flagged {key} for review: {conflict.reason}")
                # Still store but maybe mark for review in future
            # KEEP_BOTH: do nothing, store alongside
        
        # Store the memory
        return self.store_memory(
            user_id=user_id,
            key=key,
            value=final_value,
            confidence=confidence,
            source=source,
            ttl_hours=ttl_hours,
            category=category,
            allow_duplicates=False
        )

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
    mid = mm.store_memory(uid, 'learning_goal', 'Complete ACIM 365 lessons', confidence=1.0)
    print('stored', mid)
    print(mm.get_memory(uid, 'learning_goal'))
