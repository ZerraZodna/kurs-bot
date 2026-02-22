from __future__ import annotations
from typing import Optional

from src.models.database import User
from src.memories import MemoryManager
from src.memories.memory_handler import MemoryHandler
from src.memories.lesson_state import set_current_lesson


def create_test_user(db, external_id: str, first_name: Optional[str] = None) -> int:
    """Create a fresh user row for tests (does NOT add onboarding memories).

    Removes any existing user with the same external_id, creates a new
    `User` row and returns the `user_id`.
    """
    from src.models.database import Schedule

    existing = db.query(User).filter_by(external_id=external_id).first()
    if existing:
        MemoryHandler(db).delete_user_memories(existing.user_id)
        db.query(Schedule).filter_by(user_id=existing.user_id).delete()
        db.query(User).filter_by(user_id=existing.user_id).delete()
        db.commit()

    user = User(
        external_id=external_id,
        channel="test",
        phone_number=None,
        email=f"{external_id}@example.com",
        first_name=first_name if first_name and str(first_name).strip() else None,
        last_name="User",
        opted_in=True,
    )
    db.add(user)
    db.commit()
    # Also add a profile memory for first_name so tests that expect
    # onboarding prompts to consider the name don't need to rely on
    # DB-only fields. This keeps onboarding logic pure and test helpers
    # responsible for seeding memories.
    # Only store a first_name memory when a non-empty name is provided
    if first_name and str(first_name).strip():
        mm = MemoryManager(db)
        mm.store_memory(user.user_id, "first_name", first_name, category="profile", source="test")

    return user.user_id


def make_ready_user(db, external_id: str, first_name: str = "Test") -> int:
    """Create a fresh user and mark onboarding complete for tests.

    This helper calls `create_test_user` then stores the minimum memories
    required so `OnboardingService.get_onboarding_status()` returns complete.
    Returns the created `user_id`.
    """
    user_id = create_test_user(db, external_id, first_name)
    mm = MemoryManager(db)
    mm.store_memory(user_id, "acim_commitment", "yes", category="profile", source="test")
    mm.store_memory(user_id, "data_consent", "yes", category="profile", source="test")
    mm.store_memory(user_id, "first_name", first_name, category="profile", source="test")
    set_current_lesson(mm, user_id, 1)
    return user_id
