"""
Test Norwegian Language Onboarding

Verifies that when a new user writes in Norwegian,
the bot responds in Norwegian.

Test case:
  User: "Hei! Jeg heter Johannes"
  Expected: Bot responds in Norwegian
"""

import asyncio
import sys
import pytest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.database import SessionLocal, User, init_db
from src.services.dialogue_engine import DialogueEngine
from src.onboarding.service import OnboardingService
from datetime import datetime, timezone
from tests.utils import create_test_user


@pytest.mark.asyncio
async def test_norwegian_response():
    """Test that Norwegian input gets Norwegian response."""
    print("\n" + "=" * 80)
    print("TEST: Norwegian Language Onboarding")
    print("=" * 80)
    
    db = SessionLocal()
    try:
        user_id = create_test_user(db, "test_norwegian_user", first_name=None)
        
        dialogue = DialogueEngine(db)
        onboarding = OnboardingService(db)
        
        # Norwegian greeting with name
        print("\nTest: New Norwegian speaker introduces themselves")
        print("-" * 80)
        norwegian_msg = "Hei! Jeg heter Johannes"
        print(f"User (Norwegian): {norwegian_msg}")
        
        response = await dialogue.process_message(user_id, norwegian_msg, db)
        print(f"\nBot response:\n{response}\n")
        
        # Check onboarding status
        status = onboarding.get_onboarding_status(user_id)
        print(f"Onboarding status: {status}")
        
        # Check if name was extracted in Norwegian context
        name_memories = dialogue.memory_manager.get_memory(user_id, "first_name")
        print(f"\nExtracted name: {name_memories}")
        
        # Verify response is in Norwegian
        print("\n" + "-" * 80)
        print("VERIFICATION:")
        print("-" * 80)
        
        norwegian_words = [
            "lagrer", "samtalen", 
            "jeg", "her", "at", "støtte", "deg", "åndelige", "reisen", "hva",
        ]
        
        response_lower = response.lower()
        found_norwegian = [word for word in norwegian_words if word in response_lower]
        
        if len(found_norwegian) >= 3:
            print(f"✅ PASS: Response contains Norwegian words: {found_norwegian}")
            return True
        else:
            print(f"❌ FAIL: Response appears to be in English, not Norwegian")
            print(f"   Found words: {found_norwegian}")
            print(f"   Response: {response[:200]}...")
            return False
            
    finally:
        db.close()


@pytest.mark.asyncio
async def test_onboarding_norwegian_consent_print():
    """Send 'Hei', 'Johannes', then answer 'Ja' to the consent prompt and print bot response."""
    db = SessionLocal()
    try:
        user_id = create_test_user(db, "test_norwegian_user", first_name=None)
        dialogue = DialogueEngine(db)

        # Step 1: greeting
        await dialogue.process_message(user_id, "Hei", db)

        # Step 2: provide name
        await dialogue.process_message(user_id, "Johannes", db)

        # Step 3: answer consent question with 'Ja'
        consent_msg = "Ja"
        print(f"\nUser: {consent_msg}")
        response = await dialogue.process_message(user_id, consent_msg, db)

        # Print the bot response so the test output shows it
        print("\n--- BOT RESPONSE TO CONSENT START ---\n")
        print(response)
        print("\n--- BOT RESPONSE TO CONSENT END ---\n")

        assert response and isinstance(response, str)
    finally:
        db.close()


async def main():
    """Run the test."""
    try:
        success = await test_norwegian_response()
        
        print("\n" + "=" * 80)
        if success:
            print("✅ RESULT: Language detection working correctly!")
        else:
            print("❌ RESULT: Language detection needs fixing")
        print("=" * 80)
        
    except Exception as e:
        print(f"\n❌ ERROR: {e}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    print("\nTesting Norwegian language onboarding...")
    print("Make sure Ollama is running with the correct model loaded.\n")
    asyncio.run(main())


@pytest.mark.asyncio
async def test_onboarding_norwegian_hi_print():
    """Send a single-word Norwegian greeting and print the bot response."""
    db = SessionLocal()
    try:
        user_id = create_test_user(db, "test_norwegian_user", first_name=None)
        dialogue = DialogueEngine(db)

        # Send a short Norwegian greeting and capture response
        user_msg = "Hei"
        print(f"\nUser: {user_msg}")
        response = await dialogue.process_message(user_id, user_msg, db)

        # Print the bot response so the test output shows it
        print("\n--- BOT RESPONSE START ---\n")
        print(response)
        print("\n--- BOT RESPONSE END ---\n")

        assert response and isinstance(response, str)
    finally:
        db.close()


@pytest.mark.asyncio
async def test_onboarding_norwegian_name_print():
    """Send 'Hei' then the name 'Johannes' and print the bot response to the name."""
    db = SessionLocal()
    try:
        user_id = create_test_user(db, "test_norwegian_user", first_name=None)
        dialogue = DialogueEngine(db)

        # Step 1: greeting
        greeting = "Hei"
        await dialogue.process_message(user_id, greeting, db)

        # Step 2: provide name
        name_msg = "Johannes"
        print(f"\nUser: {name_msg}")
        response = await dialogue.process_message(user_id, name_msg, db)

        # Print the bot response
        print("\n--- BOT RESPONSE TO NAME START ---\n")
        print(response)
        print("\n--- BOT RESPONSE TO NAME END ---\n")

        assert response and isinstance(response, str)
    finally:
        db.close()
