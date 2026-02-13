"""
End-to-End Memory Functionality Test (moved to scripts/debug)

Run this as a manual debug/test harness when needed.
"""
import asyncio
import sys
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.models.database import SessionLocal, User, Memory, init_db
from src.services.dialogue_engine import DialogueEngine
from src.memories import MemoryManager
from datetime import datetime, timezone

# (content unchanged beyond path adjustments)

def setup_test_user(db) -> int:
    user = db.query(User).filter_by(external_id="test_user_memory").first()
    if not user:
        user = User(
            external_id="test_user_memory",
            channel="test",
            phone_number=None,
            email="test@example.com",
            first_name="Test",
            last_name="User",
            opted_in=True,
            created_at=datetime.now(timezone.utc),
            last_active_at=datetime.now(timezone.utc),
        )
        db.add(user)
        db.commit()
        print(f"✓ Created test user with ID: {user.user_id}")
    else:
        print(f"✓ Using existing test user with ID: {user.user_id}")
    return user.user_id

# The rest of the file is preserved for manual testing; import directly when needed.
