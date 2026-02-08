import pytest
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.database import SessionLocal, User, Memory, init_db
from src.services.dialogue_engine import DialogueEngine
from src.services.onboarding_service import OnboardingService


def create_new_test_user(db) -> int:
    existing = db.query(User).filter_by(external_id="test_onboarding_lang_user").first()
    if existing:
        # remove existing user and related memories
        db.query(Memory).filter_by(user_id=existing.user_id).delete()
        db.query(User).filter_by(user_id=existing.user_id).delete()
        db.commit()

    user = User(
        external_id="test_onboarding_lang_user",
        channel="test",
        phone_number=None,
        email="onboarding_lang_test@example.com",
        first_name=None,
        last_name=None,
        opted_in=True,
        created_at=datetime.now(timezone.utc),
        last_active_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    return user.user_id


@pytest.mark.asyncio
async def test_onboarding_uses_detected_language_for_prompts():
    """Send 'Hei' and expect Norwegian onboarding prompt after language detection."""
    db = SessionLocal()
    try:
        init_db()
        user_id = create_new_test_user(db)

        dialogue = DialogueEngine(db)
        onboarding = OnboardingService(db)

        # Send a Norwegian greeting which should trigger language detection
        resp = await dialogue.process_message(user_id, "Hei", db)

        # Memory should be created with value 'Norwegian'
        mems = db.query(Memory).filter_by(user_id=user_id, key="user_language").all()
        assert len(mems) > 0, "Expected a user_language memory to be stored"
        assert any(m.value == "Norwegian" for m in mems), f"Expected stored language 'Norwegian', got {[m.value for m in mems]}"

        # The onboarding response should be in Norwegian (contains typical Norwegian prompt)
        assert (
            "Hva heter" in resp or "Velkommen" in resp or "Før vi fortsetter" in resp
        ), f"Onboarding response was not Norwegian: {resp}"

    finally:
        db.close()
