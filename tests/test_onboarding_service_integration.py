from src.memories import MemoryManager
from src.onboarding import OnboardingService
from src.models.database import SessionLocal
from src.memories.lesson_state import get_current_lesson


def test_persist_explicit_lesson_number():
    session = SessionLocal()
    mm = MemoryManager(session)
    svc = OnboardingService(session)

    user_id = 42

    # Ensure no current_lesson initially
    assert get_current_lesson(mm, user_id) is None

    # User indicates an explicit lesson
    res = svc.handle_lesson_status_response(user_id, "I am on lesson 6")
    assert res["action"] == "send_specific_lesson"

    cur = get_current_lesson(mm, user_id)
    assert cur == 6


def test_persist_continuing_when_completed_before():
    session = SessionLocal()
    mm = MemoryManager(session)
    svc = OnboardingService(session)

    user_id = 43

    # User says they've completed the course
    res = svc.handle_lesson_status_response(user_id, "I've completed the course")
    assert res["action"] == "ask_lesson_number"

    cur = get_current_lesson(mm, user_id)
    assert cur == "continuing"
