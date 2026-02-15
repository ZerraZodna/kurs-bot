import asyncio

from src.memories import MemoryManager
from src.onboarding import OnboardingService
from src.onboarding.flow import OnboardingFlow
from src.models.database import SessionLocal
from src.onboarding import schedule_setup


async def _run_flow_step(flow, user_id, text, session):
    return await flow.handle_onboarding(user_id, text, session)


def test_onboarding_schedule_created_after_user_reports_lesson():
    session = SessionLocal()
    mm = MemoryManager(session)
    svc = OnboardingService(session)
    # call_ollama not used in onboarding flow for this test
    flow = OnboardingFlow(mm, svc, call_ollama=None)

    user_id = 1001

    # Ensure user has name, consent and commitment so flow reaches lesson_status
    mm.store_memory(user_id, "first_name", "Test", category="profile")
    mm.store_memory(user_id, "data_consent", "granted", category="profile")
    mm.store_memory(user_id, "acim_commitment", "committed to ACIM lessons", category="goals")

    # Step 1: user indicates they've completed the course -> flow should ask for lesson number
    resp1 = asyncio.run(_run_flow_step(flow, user_id, "I've completed the course before", session))
    assert isinstance(resp1, str)
    assert "lesson" in resp1.lower() or "which lesson" in resp1.lower()

    # Step 2: user provides explicit lesson number -> flow should deliver and create schedule
    resp2 = asyncio.run(_run_flow_step(flow, user_id, "I am on lesson 6", session))
    # After delivery, schedule should exist (07:30 default)
    sched = schedule_setup.check_existing_schedule(session, user_id)
    assert sched is not None, "Expected an auto-created daily schedule after user reported a lesson"
