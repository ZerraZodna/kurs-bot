#!/usr/bin/env python
"""Debug schedule creation issue"""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from src.services.onboarding_service import OnboardingService
from src.services.dialogue_engine import DialogueEngine
from src.models.database import SessionLocal, Memory

db = SessionLocal()

user_id = 1

# Check onboarding status
onboarding = OnboardingService(db)
status = onboarding.get_onboarding_status(user_id)

print("=" * 80)
print("SCHEDULE CREATION DEBUG")
print("=" * 80)

print("\nOnboarding Status:")
print(f"  Complete: {status['onboarding_complete']}")
print(f"  Has name: {status['has_name']}")
print(f"  Has commitment: {status['has_commitment']}")
print(f"  Next step: {status['next_step']}")
print(f"  Steps completed: {status['steps_completed']}")

# Check if schedule request is detected
test_message = "Ja, jeg ønsker gjøre leksene hver dag. Kan du minne meg på det?"
is_schedule_request = onboarding.detect_schedule_request(test_message)

print(f"\nSchedule Request Detection:")
print(f"  Message: {test_message}")
print(f"  Is schedule request: {is_schedule_request}")

# Check memories
print("\nMemories:")
memories = db.query(Memory).filter_by(user_id=user_id, is_active=True).all()
for mem in memories:
    print(f"  {mem.key}: {mem.value}")

# Check if commitment keywords are detected
is_commitment = onboarding.detect_commitment_keywords(test_message)
print(f"\nCommitment Keywords Detected: {is_commitment}")

print("\n" + "=" * 80)
