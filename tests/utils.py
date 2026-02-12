from src.models.database import User
from src.memories import MemoryManager


def create_test_user(db, external_id: str, first_name: str = "Test") -> int:
    """Create a fresh user row for tests (does NOT add onboarding memories).

    Removes any existing user with the same external_id, creates a new
    `User` row and returns the `user_id`.
    """
    from src.models.database import Memory, Schedule

    existing = db.query(User).filter_by(external_id=external_id).first()
    if existing:
        db.query(Memory).filter_by(user_id=existing.user_id).delete()
        db.query(Schedule).filter_by(user_id=existing.user_id).delete()
        db.query(User).filter_by(user_id=existing.user_id).delete()
        db.commit()

    user = User(
        external_id=external_id,
        channel="test",
        phone_number=None,
        email=f"{external_id}@example.com",
        first_name=first_name,
        last_name="User",
        opted_in=True,
    )
    db.add(user)
    db.commit()
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
    mm.store_memory(user_id, "current_lesson", "1", category="progress", source="test")
    return user_id
