from src.memories import MemoryManager
from src.onboarding import OnboardingService
from src.models.database import SessionLocal


def test_persist_explicit_lesson_number():
    session = SessionLocal()
    mm = MemoryManager(session)
    svc = OnboardingService(session)

    user_id = 42

    # Ensure no current_lesson initially
    assert mm.get_memory(user_id, "current_lesson") == []

    # User indicates an explicit lesson
    res = svc.handle_lesson_status_response(user_id, "I am on lesson 6")
    assert res["action"] == "send_specific_lesson"

    mems = mm.get_memory(user_id, "current_lesson")
    assert mems, "current_lesson was not persisted"
    assert mems[0]["value"] == "6"


def test_persist_continuing_when_completed_before():
    session = SessionLocal()
    mm = MemoryManager(session)
    svc = OnboardingService(session)

    user_id = 43

    # User says they've completed the course
    res = svc.handle_lesson_status_response(user_id, "I've completed the course")
    assert res["action"] == "ask_lesson_number"

    mems = mm.get_memory(user_id, "current_lesson")
    assert mems, "current_lesson was not persisted for continuing user"
    assert mems[0]["value"] == "continuing"
