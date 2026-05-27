#!/usr/bin/env python3
"""Integration test for practice reminders feature.

Simulates the full flow end-to-end:
1. AI extracts practice instructions for a lesson (triggers real LLM call)
2. Simulates scheduler delivering lesson + asking question
3. Simulates user saying "yes" → creates hourly reminders
4. Simulates user saying "stop reminders" → cancels them
5. Simulates user saying "yes" again → reminders created
6. Simulates /stop_daily_reminders → all cancelled

Requires live LLM connection (Ollama or OpenAI, per config).
Run once to verify the full flow works.

Usage:
    python scripts/debug/debug_practice_reminders.py [user_id] [lesson_id]
"""

import json
import sys
from datetime import datetime, UTC
from pathlib import Path

# Ensure repo root is on path for src imports
repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.models.database import Memory, Schedule, SessionLocal, User, init_db
from src.lessons.practice_extractor import check_and_extract_practice_instructions
from src.scheduler.execution import _maybe_ask_practice_reminders
from src.scheduler.reminder_manager import create_reminders, stop_daily_reminders
from src.memories import MemoryManager
from src.memories.constants import MemoryKey


def dump_state(db, user_id: int):
    """Print current user state."""
    print(f"\n{'=' * 80}")
    print(f"=== User {user_id} state ({datetime.now(tz=UTC).isoformat()}) ===")
    print(f"{'=' * 80}")

    user = db.query(User).filter_by(user_id=user_id).first()
    if not user:
        print("❌ User not found")
        return

    print(f"👤 {user.first_name} {user.last_name} — lesson={user.lesson}, tz={user.timezone}")

    # Practice-related memories
    print("\n🧠 Practice reminder memories:")
    practice_keys = [
        MemoryKey.PRACTICE_REMINDER_PENDING,
        MemoryKey.PRACTICE_REMINDER_DECLINED_TODAY,
        MemoryKey.PRACTICE_REMINDER_EVENING_CUTOFF,
    ]
    mems = (
        db.query(Memory)
        .filter(Memory.user_id == user_id, Memory.key.in_(practice_keys))
        .order_by(Memory.created_at.desc())
        .all()
    )
    if mems:
        for m in mems:
            print(f"  {m.key}: {m.value}")
    else:
        print("  (none)")

    # Schedules
    print("\n📅 Active schedules:")
    schedules = (
        db.query(Schedule)
        .filter_by(user_id=user_id, is_active=True)
        .order_by(Schedule.created_at.desc())
        .all()
    )
    if not schedules:
        print("  (none)")
    else:
        for s in schedules:
            lesson_title = s.lesson.title if s.lesson else "None"
            next_time = s.next_send_time.isoformat() if s.next_send_time else "N/A"
            print(f"  [{s.schedule_type}] id={s.schedule_id}, lesson='{lesson_title}', next={next_time}")

    print(f"{'=' * 80}\n")


def step(label: str, text: str = ""):
    """Print a step header."""
    print(f"\n{'─' * 60}")
    print(f"  STEP: {label}")
    if text:
        print(f"         {text}")
    print(f"{'─' * 60}")


def main():
    user_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    lesson_id = int(sys.argv[2]) if len(sys.argv) > 2 else 104

    print("🧪 Practice Reminders Integration Test")
    print(f"   User: {user_id}  |  Lesson: {lesson_id}")
    print("   LLM: live connection required\n")

    db = SessionLocal()
    try:
        init_db()

        # Verify user exists
        user = db.query(User).filter_by(user_id=user_id).first()
        if not user:
            print(f"❌ User {user_id} not found. Exiting.")
            return

        # Clean slate
        step("0. Clean slate", "Clearing any existing practice reminder state")
        mm = MemoryManager(db)
        for key in [MemoryKey.PRACTICE_REMINDER_PENDING, MemoryKey.PRACTICE_REMINDER_DECLINED_TODAY]:
            mems = mm.get_memory(user_id, key)
            for m in mems:
                mm.archive_memories(user_id, [m["memory_id"]])
        # Deactivate any existing one-time practice reminders
        stop_daily_reminders(user_id, session=db)
        print("✅ Clean slate done\n")

        # Step 1: AI extraction
        step("1. AI extracts practice instructions", f"Calling LLM to analyze lesson {lesson_id}")
        instructions = check_and_extract_practice_instructions(lesson_id, session=db)
        if not instructions:
            print("❌ Extraction failed (lesson not found). Exiting.")
            return

        print(f"✅ Extracted: {json.dumps(instructions, indent=2)}")

        # Verify it was cached
        cached = check_and_extract_practice_instructions(lesson_id, session=db)
        assert cached == instructions, "Cached result doesn't match extraction!"
        print("✅ Cache verified — second call returns same result\n")

        # Step 2: Simulate lesson delivery + ask question
        step("2. Simulate lesson delivery + ask question", "Scheduler delivers lesson, bot asks about reminders")

        # Need a User object for _maybe_ask_practice_reminders
        from src.models.database import User as UserModel

        user_obj = db.query(UserModel).filter_by(user_id=user_id).first()

        _maybe_ask_practice_reminders(db, user_id, mm, user_obj)

        # Check if question was asked
        pending = mm.get_memory(user_id, MemoryKey.PRACTICE_REMINDER_PENDING)
        if pending:
            print(f"✅ Bot asked the question. Pending lesson_id: {pending[0]['value']}")
        else:
            print("ℹ️  No question asked (lesson frequency is 'single' or user already declined)\n")
            dump_state(db, user_id)
            return

        # Step 3: User says "yes"
        step("3. User says 'yes'", "Creating hourly reminders")
        mm.store_memory(
            user_id=user_id,
            key=MemoryKey.PRACTICE_REMINDER_PENDING,
            value=str(lesson_id),
            ttl_hours=1,
            category="conversation",
        )
        result = create_reminders(lesson_id, user_id, instructions, session=db)
        print(f"✅ Created {len(result)} reminder(s)")

        for s in result[:5]:  # Show first 5
            lesson_title = s.lesson.title if s.lesson else "None"
            next_time = s.next_send_time.isoformat() if s.next_send_time else "N/A"
            print(f"   [{s.schedule_type}] lesson='{lesson_title}', next={next_time}")
        if len(result) > 5:
            print(f"   ... and {len(result) - 5} more")

        dump_state(db, user_id)

        # Step 4: User says "stop reminders"
        step("4. User says 'stop reminders'", "Cancelling all active practice reminders")
        count = stop_daily_reminders(user_id, session=db)
        print(f"✅ Stopped {count} reminder(s)")
        dump_state(db, user_id)

        # Step 5: User says "yes" again (via start reminders)
        step("5. User says 'start reminders'", "Re-creating reminders after stopping")
        result2 = create_reminders(lesson_id, user_id, instructions, session=db)
        print(f"✅ Created {len(result2)} reminder(s)")
        dump_state(db, user_id)

        # Step 6: Final stop
        step("6. Final stop", "Cleaning up all reminders")
        count = stop_daily_reminders(user_id, session=db)
        print(f"✅ Stopped {count} reminder(s)")
        dump_state(db, user_id)

        print("\n🎉 All steps completed successfully!")
        print("   The practice reminders feature is working end-to-end.")

    finally:
        db.close()


if __name__ == "__main__":
    main()
