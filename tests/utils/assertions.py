"""Assertion helpers for tests.

Provides standardized assertion functions for common test scenarios.
These make tests more readable and reduce duplication.
"""

from typing import List

from sqlalchemy.orm import Session

from src.models.database import Memory, MessageLog, Schedule, User


def assert_memory_stored(
    db: Session,
    user_id: int,
    key: str,
    expected_value: str | None = None,
    category: str | None = None,
    is_active: bool = True,
) -> Memory:
    """Assert that a memory exists with the given criteria.

    Args:
        db: Database session
        user_id: User ID to check
        key: Memory key to look for
        expected_value: Optional value to match
        category: Optional category to match
        is_active: Whether memory should be active (default: True)

    Returns:
        The found Memory object

    Raises:
        AssertionError: If memory not found or doesn't match criteria
    """
    query = db.query(Memory).filter_by(user_id=user_id, key=key, is_active=is_active)

    memory = query.first()

    assert memory is not None, f"Memory with key '{key}' not found for user {user_id} (is_active={is_active})"

    if expected_value is not None:
        assert memory.value == expected_value, (
            f"Memory value mismatch for key '{key}': expected '{expected_value}', got '{memory.value}'"
        )

    if category is not None:
        assert memory.category == category, (
            f"Memory category mismatch for key '{key}': expected '{category}', got '{memory.category}'"
        )

    return memory


def assert_memory_count(
    db: Session,
    user_id: int,
    expected_count: int,
    key: str | None = None,
    is_active: bool | None = None,
) -> List[Memory]:
    """Assert that a specific number of memories exist.

    Args:
        db: Database session
        user_id: User ID to check
        expected_count: Expected number of memories
        key: Optional key filter
        is_active: Optional active status filter

    Returns:
        List of found Memory objects

    Raises:
        AssertionError: If count doesn't match
    """
    query = db.query(Memory).filter_by(user_id=user_id)

    if key is not None:
        query = query.filter_by(key=key)

    if is_active is not None:
        query = query.filter_by(is_active=is_active)

    memories = query.all()
    actual_count = len(memories)

    assert actual_count == expected_count, (
        f"Expected {expected_count} memories for user {user_id}, "
        f"found {actual_count}"
        + (f" with key='{key}'" if key else "")
        + (f" (is_active={is_active})" if is_active is not None else "")
    )

    return memories


def assert_schedule_created(
    db: Session,
    user_id: int,
    schedule_type: str,
    is_active: bool = True,
) -> Schedule:
    """Assert that a schedule exists for the user.

    Args:
        db: Database session
        user_id: User ID to check
        schedule_type: Type of schedule (e.g., "daily", "one_time")
        is_active: Whether schedule should be active (default: True)

    Returns:
        The found Schedule object

    Raises:
        AssertionError: If schedule not found
    """
    schedule = db.query(Schedule).filter_by(user_id=user_id, schedule_type=schedule_type, is_active=is_active).first()

    assert schedule is not None, (
        f"Schedule of type '{schedule_type}' not found for user {user_id} (is_active={is_active})"
    )

    return schedule


def assert_schedule_count(
    db: Session,
    user_id: int,
    expected_count: int,
    is_active: bool | None = None,
) -> List[Schedule]:
    """Assert that a specific number of schedules exist.

    Args:
        db: Database session
        user_id: User ID to check
        expected_count: Expected number of schedules
        is_active: Optional active status filter

    Returns:
        List of found Schedule objects
    """
    query = db.query(Schedule).filter_by(user_id=user_id)

    if is_active is not None:
        query = query.filter_by(is_active=is_active)

    schedules = query.all()
    actual_count = len(schedules)

    assert actual_count == expected_count, (
        f"Expected {expected_count} schedules for user {user_id}, "
        f"found {actual_count}" + (f" (is_active={is_active})" if is_active is not None else "")
    )

    return schedules


def assert_message_logged(
    db: Session,
    user_id: int,
    direction: str,
    content_contains: str | None = None,
) -> MessageLog:
    """Assert that a message was logged.

    Args:
        db: Database session
        user_id: User ID to check
        direction: Message direction ("inbound" or "outbound")
        content_contains: Optional string to check in content

    Returns:
        The found MessageLog object

    Raises:
        AssertionError: If message not found
    """
    log = (
        db
        .query(MessageLog)
        .filter_by(user_id=user_id, direction=direction)
        .order_by(MessageLog.created_at.desc())
        .first()
    )

    assert log is not None, f"No {direction} message found for user {user_id}"

    if content_contains is not None:
        assert content_contains in log.content, f"Message content doesn't contain '{content_contains}': {log.content}"

    return log


def assert_onboarding_step(
    db: Session,
    user_id: int,
    expected_step: str,
) -> None:
    """Assert that user is at a specific onboarding step.

    Args:
        db: Database session
        user_id: User ID to check
        expected_step: Expected onboarding step name

    Raises:
        AssertionError: If step doesn't match
    """
    from src.onboarding.service import OnboardingService

    onboarding = OnboardingService(db)
    status = onboarding.get_onboarding_status(user_id)

    actual_step = status.get("current_step")
    assert actual_step == expected_step, f"Expected onboarding step '{expected_step}', got '{actual_step}'"


def assert_onboarding_complete(db: Session, user_id: int) -> None:
    """Assert that user has completed onboarding.

    Args:
        db: Database session
        user_id: User ID to check

    Raises:
        AssertionError: If onboarding not complete
    """
    from src.onboarding.service import OnboardingService

    onboarding = OnboardingService(db)
    status = onboarding.get_onboarding_status(user_id)

    is_complete = status.get("onboarding_complete", False)
    assert is_complete, (
        f"Expected onboarding to be complete for user {user_id}, but current_step is '{status.get('current_step')}'"
    )


def assert_user_exists(db: Session, external_id: str) -> User:
    """Assert that a user exists with the given external_id.

    Args:
        db: Database session
        external_id: External ID to look up

    Returns:
        The found User object

    Raises:
        AssertionError: If user not found
    """
    user = db.query(User).filter_by(external_id=external_id).first()

    assert user is not None, f"User with external_id '{external_id}' not found"

    return user


def assert_response_contains(response: str, *expected_substrings: str) -> None:
    """Assert that response contains all expected substrings.

    Args:
        response: The response text to check
        *expected_substrings: Substrings that must be present

    Raises:
        AssertionError: If any substring is missing
    """
    for substring in expected_substrings:
        assert substring in response, f"Response doesn't contain '{substring}': {response[:200]}..."


def assert_response_matches_any(response: str, *expected_options: str) -> None:
    """Assert that response matches at least one of the expected options.

    Args:
        response: The response text to check
        *expected_options: Substrings, any one of which must be present

    Raises:
        AssertionError: If none of the options match
    """
    matches = [opt for opt in expected_options if opt in response]
    assert matches, (
        f"Response doesn't match any expected options. "
        f"Response: {response[:200]}... "
        f"Expected one of: {expected_options}"
    )
