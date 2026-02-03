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
from src.services.onboarding_service import OnboardingService
from datetime import datetime, timezone


def create_norwegian_test_user(db) -> int:
    """Create a fresh Norwegian-speaking test user."""
    # Delete existing test user if exists
    existing_user = db.query(User).filter_by(external_id="test_norwegian_user").first()
    if existing_user:
        from src.models.database import Memory, Schedule
        db.query(Memory).filter_by(user_id=existing_user.user_id).delete()
        db.query(Schedule).filter_by(user_id=existing_user.user_id).delete()
        db.query(User).filter_by(user_id=existing_user.user_id).delete()
        db.commit()
    
    user = User(
        external_id="test_norwegian_user",
        channel="test",
        phone_number=None,
        email="norwegian_test@example.com",
        first_name=None,
        last_name=None,
        opted_in=True,
        created_at=datetime.now(timezone.utc),
        last_active_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user.user_id


@pytest.mark.asyncio
async def test_norwegian_response():
    """Test that Norwegian input gets Norwegian response."""
    print("\n" + "=" * 80)
    print("TEST: Norwegian Language Onboarding")
    print("=" * 80)
    
    db = SessionLocal()
    try:
        user_id = create_norwegian_test_user(db)
        
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
            "herlig", "du", "interessert", "utforske", "disse", "leksjonene", "sammen",
            "jeg", "her", "veilede", "støtte", "deg", "åndelige", "reisen", "hva",
            "heter", "ditt", "navn", "ønsker", "lykke", "velkommen", "dag", "lærer",
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
