"""
Test Onboarding and Scheduling Flow

Tests the complete user journey:
1. User arrives (new user) - gets name prompt
2. User provides name - gets consent prompt  
3. User consents to data storage - gets commitment prompt
4. User commits to 365 lessons - gets lesson status prompt
5. User provides lesson status - gets lesson 1 and completes onboarding
6. Schedule is auto-created
"""

import asyncio
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.database import SessionLocal, User, init_db
from tests.utils import create_test_user
from src.services.dialogue_engine import DialogueEngine
from src.onboarding.service import OnboardingService
from src.scheduler import SchedulerService
from datetime import datetime, timezone
from src.language.onboarding_prompts_legacy import get_onboarding_message
from src.memories import MemoryManager
from uuid import uuid4


@pytest.mark.asyncio
async def test_onboarding_flow():
    """Test complete onboarding flow."""
    print("\n" + "=" * 80)
    print("TEST: Complete Onboarding Flow")
    print("=" * 80)
    
    db = SessionLocal()
    user_id = create_test_user(db, "test_onboarding_user-1")
    
    dialogue = DialogueEngine(db)
    onboarding = OnboardingService(db)
    
    # Step 1: First message - should get welcome prompt
    print("\n[Step 1] User's first message")
    print("-" * 80)
    user_msg = "Hi there!"
    print(f"User: {user_msg}")
    
    response = await dialogue.process_message(user_id, user_msg, db)
    print(f"Bot: {response[:150]}...")
    
    # Check onboarding status
    status = onboarding.get_onboarding_status(user_id)
    print(f"\nOnboarding status: {status}")
    
    # Step 2: User provides name
    print("\n[Step 2] User provides name")
    print("-" * 80)
    user_msg = "My name is Sarah"
    print(f"User: {user_msg}")
    
    response = await dialogue.process_message(user_id, user_msg, db)
    print(f"Bot: {response[:200]}...")
    
    status = onboarding.get_onboarding_status(user_id)
    print(f"\nOnboarding status: {status}")
    
    # Step 3: User consents to data storage
    print("\n[Step 3] User consents to data storage")
    print("-" * 80)
    user_msg = "Yes, I consent"
    print(f"User: {user_msg}")
    
    response = await dialogue.process_message(user_id, user_msg, db)
    print(f"Bot: {response[:200]}...")
    
    status = onboarding.get_onboarding_status(user_id)
    print(f"\nOnboarding status: {status}")
    
    # Step 4: User commits to lessons
    print("\n[Step 4] User commits to 365 lessons")
    print("-" * 80)
    user_msg = "Yes, I'm ready to commit to this journey!"
    print(f"User: {user_msg}")
    
    response = await dialogue.process_message(user_id, user_msg, db)
    print(f"Bot: {response[:200]}...")
    
    status = onboarding.get_onboarding_status(user_id)
    print(f"\nOnboarding status: {status}")
    
    # Step 5: User provides lesson status (new vs continuing)
    print("\n[Step 5] User indicates they're new to ACIM")
    print("-" * 80)
    user_msg = "I'm new to ACIM"
    print(f"User: {user_msg}")
    
    response = await dialogue.process_message(user_id, user_msg, db)
    print(f"Bot: {response[:300]}...")
    
    status = onboarding.get_onboarding_status(user_id)
    print(f"\nOnboarding status: {status}")
    
    # Check if schedule was auto-created (should be created at completion)
    schedules = SchedulerService.get_user_schedules(user_id)
    print(f"\n📅 Schedules created: {len(schedules)}")
    for schedule in schedules:
        print(f"  • Schedule ID: {schedule.schedule_id}")
        print(f"    Type: {schedule.schedule_type}")
        print(f"    Cron: {schedule.cron_expression}")
        print(f"    Next send: {schedule.next_send_time}")
        print(f"    Active: {schedule.is_active}")
    
    if status["onboarding_complete"] and len(schedules) > 0:
        print("\n✅ SUCCESS: Onboarding complete and auto-schedule created!")
        return True
    else:
        print("\n❌ FAILED: Onboarding not complete or schedule not auto-created")
        print(f"    Onboarding complete: {status['onboarding_complete']}")
        print(f"    Schedules: {len(schedules)}")
        return False
        
    db.close()


@pytest.mark.asyncio
async def test_consent_granted_continues_onboarding():
    """Ensure consenting returns a localized thank-you and continues onboarding."""
    db = SessionLocal()
    user_id = create_test_user(db, "test_onboarding_user-2")

    dialogue = DialogueEngine(db)
    onboarding = OnboardingService(db)

    # Trigger name prompt and provide name
    response = await dialogue.process_message(user_id, "Hi", db)
    print(response)
    response = await dialogue.process_message(user_id, "My name is Alex", db)
    print(response)

    # Provide consent
    user_msg = "Yes"
    response = await dialogue.process_message(user_id, user_msg, db)
    print(response)

    # Response should include the localized thank-you
    assert "Thank you for consenting" in response

    # Onboarding status should now reflect consent given
    status = onboarding.get_onboarding_status(user_id)
    assert status.get("has_consent") is True

    # And the bot should continue by asking commitment (accept a few equivalent phrasings)
    assert (
        "Are you interested" in response
        or "Are you new to ACIM" in response
        or "Are you ready" in response
    )
    db.close()


@pytest.mark.asyncio
async def test_schedule_request():
    """Test that users can request reminders explicitly."""
    print("\n" + "=" * 80)
    print("TEST: Explicit Schedule Request")
    print("=" * 80)
    
    db = SessionLocal()
    user_id = create_test_user(db, "test_onboarding_user-3")
    dialogue = DialogueEngine(db)
    
    # User asks for reminders
    print("\nUser asks for reminders...")
    user_msg = "Can you remind me to do my daily lesson?"
    print(f"User: {user_msg}")
    
    response = await dialogue.process_message(user_id, user_msg, db)
    print(f"Bot: {response[:200]}...")
    
    # Check if bot is guiding them through setup
    if "commit" in response.lower() or "ready" in response.lower():
        print("\n✅ SUCCESS: Bot detected schedule request and guiding user")
        return True
    else:
        print("\n⚠️  Bot response doesn't seem to be handling schedule request")
        return False
    
    db.close()


@pytest.mark.asyncio
async def test_time_parsing():
    """Test time string parsing."""
    print("\n" + "=" * 80)
    print("TEST: Time Parsing")
    print("=" * 80)
    
    test_cases = [
        ("9:00 AM", (9, 0)),
        ("2:30 PM", (14, 30)),
        ("morning", (9, 0)),
        ("evening", (19, 0)),
        ("21:00", (21, 0)),
        ("kvelden", (19, 0)),  # Norwegian
    ]
    
    all_passed = True
    for time_str, expected in test_cases:
        result = SchedulerService.parse_time_string(time_str)
        status = "✓" if result == expected else "✗"
        print(f"{status} '{time_str}' -> {result} (expected {expected})")
        if result != expected:
            all_passed = False
    
    if all_passed:
        print("\n✅ SUCCESS: All time parsing tests passed!")
    else:
        print("\n❌ FAILED: Some time parsing tests failed")
    
    return all_passed


@pytest.mark.asyncio
async def test_onboarding_greeting_hei_detects_norwegian():
    """New user sends Norwegian greeting 'Hei' -> detect 'no' and respond in Norwegian."""
    db = SessionLocal()
    user_id = create_test_user(db, "test_onboarding_user-4")
    mm = MemoryManager(db)

    # initially no language memory
    before_lang = mm.get_memory(user_id, "user_language")
    assert not before_lang

    dialogue = DialogueEngine(db)

    # send Norwegian greeting
    response = await dialogue.process_message(user_id, "Hei", db)
    print(response)

    # after greeting, language memory should be Norwegian
    lang_memories = mm.get_memory(user_id, "user_language")
    assert lang_memories, "No user_language memory stored after greeting"
    assert any(m["value"].lower().startswith("no") for m in lang_memories), (
        f"Expected 'no' to be stored after message 'Hei', got: {[m['value'] for m in lang_memories]}"
    )

    # name memory should not yet be set
    name_mem = mm.get_memory(user_id, "first_name")
    assert not name_mem or name_mem[0].get("value") in (None, ""), "Expected no first_name memory yet"

    # The bot's response should be the Norwegian name prompt.
    # Onboarding now prefers fetching the name from Telegram when available,
    # so accept either the original templated prompt or the Telegram-autofill phrasing.
    from src.language.onboarding_prompts_legacy import get_onboarding_message
    expected = get_onboarding_message("name_prompt", "no")
    if not (expected and expected in response):
        # Accept phrasing that references the Telegram name being present
        telegram_phrase_ok = (
            "navnet ditt i Telegram" in response
            or "Jeg ser at navnet ditt i Telegram" in response
            or "kaller deg" in response
        )
        # Also accept the simpler Norwegian welcome/name prompt phrasing
        simple_norwegian_ok = (
            "Hva heter du" in response
            or "Velkommen! Hva heter du" in response
            or ("Velkommen!" in response and "Hva" in response)
        )
        assert telegram_phrase_ok or simple_norwegian_ok, (
            f"Expected Norwegian onboarding prompt (templated, Telegram-autofill, or simple welcome) in response, got: {response}"
        )

    db.close()


async def run_all_tests():
    """Run all onboarding and scheduling tests."""
    print("\n" + "=" * 80)
    print("ONBOARDING & SCHEDULING TEST SUITE")
    print("=" * 80)
    
    # Initialize scheduler (required for schedule creation)
    print("\nInitializing scheduler...")
    SchedulerService.init_scheduler()
    print("✓ Scheduler initialized")
    
    results = []
    
    # Test 1: Time parsing
    try:
        result = await test_time_parsing()
        results.append(("Time parsing", result))
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        results.append(("Time parsing", False))
    
    # Test 2: Complete onboarding flow
    try:
        result = await test_onboarding_flow()
        results.append(("Onboarding flow", result))
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        import traceback
        traceback.print_exc()
        results.append(("Onboarding flow", False))
    
    # Test 3: Explicit schedule request
    try:
        result = await test_schedule_request()
        results.append(("Schedule request", result))
    except Exception as e:
        print(f"\n❌ Test failed with error: {e}")
        results.append(("Schedule request", False))
    
    # Shutdown scheduler
    print("\nShutting down scheduler...")
    SchedulerService.shutdown()
    print("✓ Scheduler shut down")
    
    # Summary
    print("\n" + "=" * 80)
    print("TEST SUMMARY")
    print("=" * 80)
    
    passed = sum(1 for _, result in results if result)
    total = len(results)
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
    
    print(f"\nTotal: {passed}/{total} tests passed")
    
    if passed == total:
        print("\n🎉 All tests passed! Onboarding and scheduling system working!")
    else:
        print(f"\n⚠️  {total - passed} test(s) failed.")


if __name__ == "__main__":
    asyncio.run(run_all_tests())
