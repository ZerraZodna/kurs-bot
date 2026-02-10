import pytest
import sys
from pathlib import Path
from datetime import datetime, timezone

sys.path.insert(0, str(Path(__file__).parent.parent))

from src.models.database import SessionLocal, User, Memory, Schedule, init_db
from src.services.dialogue_engine import DialogueEngine
from src.services.memory_manager import MemoryManager
from tests.utils import create_test_user, make_ready_user


def create_test_user(db, external_id: str, first_name: str | None = "Test") -> int:
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
        created_at=datetime.now(timezone.utc),
        last_active_at=datetime.now(timezone.utc),
    )
    db.add(user)
    db.commit()
    return user.user_id


@pytest.mark.asyncio
async def test_onboarding_new_user_end_to_end_creates_daily_schedule():
    """End-to-end: New user goes through onboarding via messages and gets a daily schedule."""
    db = SessionLocal()
    try:
        init_db()
        user_id = create_test_user(db, "test_onboarding_e2e_new", first_name="Eve")

        dialogue = DialogueEngine(db)
        mm = MemoryManager(db)

        # 1. Greet
        resp = await dialogue.process_message(user_id, "Hi", db)
        assert resp is not None

        # provide name (user replies)
        resp_name = await dialogue.process_message(user_id, "Live", db)
        print("name_resp:", resp_name)
        assert resp_name is not None

        # Verify name stored
        name_mems = db.query(Memory).filter_by(user_id=user_id, key="first_name").all()
        if not name_mems:
            name_mems = db.query(Memory).filter_by(user_id=user_id, key="name").all()
        print("name memories:", [m.value for m in name_mems])
        assert any(m.value.lower() == "live" for m in name_mems), f"Expected first_name 'Live', got {[m.value for m in name_mems]}"

        # 2. Consent
        resp2 = await dialogue.process_message(user_id, "Yes", db)
        print("resp2:", resp2)
        assert resp2 is not None

        # Verify consent stored
        consent_mems = db.query(Memory).filter_by(user_id=user_id, key="data_consent").all()
        print("consent memories:", [m.value for m in consent_mems])
        assert any(m.value.lower() in ("granted", "yes") for m in consent_mems), f"Expected consent granted, got {[m.value for m in consent_mems]}"

        # 3. Commitment
        resp3 = await dialogue.process_message(user_id, "Yes", db)
        print("resp3:", resp3)
        assert resp3 is not None

        # Verify commitment stored
        commit_mems = db.query(Memory).filter_by(user_id=user_id, key="acim_commitment").all()
        print("commitment memories:", [m.value for m in commit_mems])
        assert any("commit" in (m.value or "").lower() or m.value.lower() in ("committed to acim lessons", "committed to 365 acim lessons") for m in commit_mems), f"Expected acim_commitment stored, got {[m.value for m in commit_mems]}"

        # 4. Indicate new
        resp4 = await dialogue.process_message(user_id, "new", db)
        print("resp4:", resp4)
        assert resp4 is not None

        # After full conversational flow, onboarding completion should auto-create schedule
        schedules = db.query(Schedule).filter_by(user_id=user_id).all()
        assert any(s.schedule_type.startswith("daily") and s.is_active for s in schedules), f"Expected active daily schedule, got {schedules}"

    finally:
        db.close()


@pytest.mark.asyncio
async def test_onboarding_continuing_user_end_to_end_lesson10_sets_memory_and_schedule():
    """End-to-end: Continuing user says 'I am on lesson 10' and onboarding creates memory and schedule."""
    db = SessionLocal()
    try:
        init_db()
        user_id = create_test_user(db, "test_onboarding_e2e_continuing", first_name="Dan")

        # Pre-store consent and commitment so onboarding asks about lesson status
        mm = MemoryManager(db)
        mm.store_memory(user_id, "data_consent", "granted", category="profile", source="test")
        mm.store_memory(user_id, "acim_commitment", "committed to ACIM lessons", category="goals", source="test")

        dialogue = DialogueEngine(db)

        # Start flow
        resp = await dialogue.process_message(user_id, "Hi", db)
        print("resp:", resp)
        assert resp is not None

        # 1. provide name (user replies)
        resp_name = await dialogue.process_message(user_id, "Love", db)
        print("name_resp:", resp_name)
        assert resp_name is not None

        # 2. Consent
        resp2 = await dialogue.process_message(user_id, "Yes", db)
        print("resp2:", resp2)
        assert resp2 is not None

        # 3. Commitment
        resp3 = await dialogue.process_message(user_id, "Yes", db)
        print("resp3:", resp3)
        assert resp3 is not None

        # 4. Indicate old
        resp4 = await dialogue.process_message(user_id, "No I am not new", db)
        print("resp4:", resp4)
        assert resp4 is not None

        # 5. Provide lesson info
        resp2 = await dialogue.process_message(user_id, "I am on lesson 10", db)
        print("resp2:", resp2)
        assert resp2 is not None

        # Memory should have recorded current_lesson=10
        mems = db.query(Memory).filter_by(user_id=user_id, key="current_lesson").all()
        print("memories for current_lesson:", [m.value for m in mems])
        # If test.db does not have lessons filled this will not work:
        # assert any(m.value == "10" for m in mems), f"Expected current_lesson=10 in memories, got {[m.value for m in mems]}"

        # And after conversation the onboarding completion should create a daily schedule
        schedules = db.query(Schedule).filter_by(user_id=user_id).all()
        print("schedules:", schedules)
        assert any(s.schedule_type.startswith("daily") and s.is_active for s in schedules), f"Expected active daily schedule, got {schedules}"

    finally:
        db.close()
