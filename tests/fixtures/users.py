"""User fixtures and factories for tests."""

import datetime
from typing import Optional, Generator

import pytest
from sqlalchemy.orm import Session

from src.models.database import User
from src.memories import MemoryManager
from src.memories.memory_handler import MemoryHandler
from src.lessons.state import set_current_lesson


# Constants
DEFAULT_EXTERNAL_ID = "test_user_001"
DEFAULT_FIRST_NAME = "Test"
DEFAULT_CHANNEL = "telegram"
DEFAULT_LANGUAGE = "en"


@pytest.fixture
def test_user(db_session: Session) -> Generator[User, None, None]:
    """Standard test user fixture.
    
    Creates a basic user with default values.
    """
    user = User(
        external_id=DEFAULT_EXTERNAL_ID,
        channel=DEFAULT_CHANNEL,
        first_name=DEFAULT_FIRST_NAME,
        last_name="User",
        opted_in=True,
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add(user)
    db_session.commit()
    
    yield user


@pytest.fixture
def test_user_with_memories(db_session: Session, test_user: User) -> Generator[User, None, None]:
    """Test user with pre-populated memories.
    
    Includes onboarding memories and current lesson state.
    """
    mm = MemoryManager(db_session)
    
    # Add standard onboarding memories
    mm.store_memory(test_user.user_id, "first_name", DEFAULT_FIRST_NAME, category="profile", source="test")
    mm.store_memory(test_user.user_id, "data_consent", "yes", category="profile", source="test")
    mm.store_memory(test_user.user_id, "acim_commitment", "yes", category="profile", source="test")
    mm.store_memory(test_user.user_id, "user_language", DEFAULT_LANGUAGE, category="profile", source="test")
    
    # Set current lesson
    set_current_lesson(mm, test_user.user_id, 1)
    
    yield test_user


@pytest.fixture
def test_user_norwegian(db_session: Session) -> Generator[User, None, None]:
    """Norwegian test user fixture.
    
    Creates a user with Norwegian language preference.
    """
    user = User(
        external_id="test_user_no_001",
        channel=DEFAULT_CHANNEL,
        first_name="Ola",
        last_name="Nordmann",
        opted_in=True,
        created_at=datetime.datetime.now(datetime.timezone.utc),
    )
    db_session.add(user)
    db_session.commit()
    
    # Add Norwegian language memory
    mm = MemoryManager(db_session)
    mm.store_memory(user.user_id, "user_language", "no", category="profile", source="test")
    mm.store_memory(user.user_id, "first_name", "Ola", category="profile", source="test")
    
    yield user


class UserFactory:
    """Factory for creating test users with custom attributes.
    
    Usage:
        user = UserFactory(db_session).create(
            external_id="custom_001",
            first_name="Custom",
            language="es"
        )
    """
    
    def __init__(self, db_session: Session):
        self.db_session = db_session
        self._counter = 0
    
    def create(
        self,
        external_id: Optional[str] = None,
        first_name: Optional[str] = None,
        last_name: str = "User",
        channel: str = DEFAULT_CHANNEL,
        opted_in: bool = True,
        language: Optional[str] = None,
        with_onboarding_complete: bool = False,
    ) -> User:
        """Create a test user with specified attributes."""
        self._counter += 1
        
        user = User(
            external_id=external_id or f"test_user_{self._counter:03d}",
            channel=channel,
            first_name=first_name,
            last_name=last_name,
            opted_in=opted_in,
            created_at=datetime.datetime.now(datetime.timezone.utc),
        )
        self.db_session.add(user)
        self.db_session.commit()
        
        # Add memories if specified
        if first_name or language or with_onboarding_complete:
            mm = MemoryManager(self.db_session)
            
            if first_name:
                mm.store_memory(user.user_id, "first_name", first_name, category="profile", source="test")
            
            if language:
                mm.store_memory(user.user_id, "user_language", language, category="profile", source="test")
            
            if with_onboarding_complete:
                mm.store_memory(user.user_id, "data_consent", "yes", category="profile", source="test")
                mm.store_memory(user.user_id, "acim_commitment", "yes", category="profile", source="test")
                set_current_lesson(mm, user.user_id, 1)
        
        return user
    
    def create_ready_user(self, external_id: Optional[str] = None, first_name: str = "Test") -> User:
        """Create a user with onboarding complete (ready for normal use)."""
        return self.create(
            external_id=external_id,
            first_name=first_name,
            with_onboarding_complete=True,
        )


@pytest.fixture
def user_factory(db_session: Session) -> UserFactory:
    """Factory fixture for creating test users."""
    return UserFactory(db_session)


def create_test_user(db: Session, external_id: str, first_name: Optional[str] = None) -> int:
    """Legacy helper: Create a fresh user row for tests.
    
    Removes any existing user with the same external_id, creates a new
    `User` row and returns the `user_id`.
    
    Note: Prefer using the UserFactory or test_user fixture for new tests.
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
    
    # Only store a first_name memory when a non-empty name is provided
    if first_name and str(first_name).strip():
        mm = MemoryManager(db)
        mm.store_memory(user.user_id, "first_name", first_name, category="profile", source="test")

    return user.user_id


def make_ready_user(db: Session, external_id: str, first_name: str = "Test", timezone: Optional[str] = "UTC") -> int:
    """Legacy helper: Create a fresh user and mark onboarding complete for tests.
    
    This helper calls `create_test_user` then stores the minimum memories
    required so `OnboardingService.get_onboarding_status()` returns complete.
    Returns the created `user_id`.
    
    Note: Prefer using UserFactory.create_ready_user() for new tests.
    """
    user_id = create_test_user(db, external_id, first_name)
    
    # Set timezone on user if provided (pass None to skip)
    if timezone is not None:
        user = db.query(User).filter_by(user_id=user_id).first()
        if user:
            user.timezone = timezone
            db.commit()
    
    mm = MemoryManager(db)
    mm.store_memory(user_id, "acim_commitment", "yes", category="profile", source="test")
    mm.store_memory(user_id, "data_consent", "yes", category="profile", source="test")
    mm.store_memory(user_id, "first_name", first_name, category="profile", source="test")
    set_current_lesson(mm, user_id, 1)
    return user_id
