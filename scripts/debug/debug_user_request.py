import asyncio
import json
import sys
from datetime import datetime
from pathlib import Path

# Ensure repo root is on path for src imports
repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.models.database import SessionLocal, User, Memory, Schedule, init_db
from src.memories import MemoryManager
from src.services.dialogue_engine import DialogueEngine


def dump_user_state(db, user_id):
    print(f"\n=== Inspecting user {user_id} state ===")
    user = db.query(User).filter_by(user_id=user_id).first()
    if not user:
        print("User not found")
        return
    

    print("User:", {"user_id": user.user_id, "external_id": user.external_id, "timezone": user.timezone, "first_name": user.first_name, "lesson": user.lesson})

    print("\nSchedules:")
    schedules = db.query(Schedule).filter_by(user_id=user_id).all()
    for s in schedules:
        print({
            "schedule_id": s.schedule_id,
            "schedule_type": s.schedule_type,
            "cron": s.cron_expression,
            "next_send_time": (s.next_send_time.isoformat() if s.next_send_time else None),
            "is_active": s.is_active,
        })

    print("\nMemories (recent 200):")
    mems = db.query(Memory).filter_by(user_id=user_id).order_by(Memory.created_at.asc()).limit(200).all()
    for m in mems:
        print({"key": m.key, "category": m.category, "value": (m.value[:200] + '...' if len(m.value) > 200 else m.value), "created_at": (m.created_at.isoformat() if m.created_at else None)})

    # Also show any schedule_message payloads specifically
    print("\nSchedule message memories:")
    sm = db.query(Memory).filter_by(user_id=user_id, key="schedule_message").order_by(Memory.created_at.asc()).all()
    for m in sm:
        print({"value": (m.value[:500] + '...' if len(m.value) > 500 else m.value), "created_at": (m.created_at.isoformat() if m.created_at else None)})


async def run_check(user_id: int, text: str):
    db = SessionLocal()
    try:
        dump_user_state(db, user_id)

        print("\nInvoking DialogueEngine.process_message()")
        dialogue = DialogueEngine(db)
        resp = await dialogue.process_message(user_id, text, db)
        print('\n--- LLM response start ---')
        print(resp)
        print('--- LLM response end ---\n')

        print("\nPost-run schedules and memories:")
        dump_user_state(db, user_id)
    finally:
        db.close()


if __name__ == '__main__':
    user_id = int(sys.argv[1]) if len(sys.argv) > 1 else 7
    text = sys.argv[2] if len(sys.argv) > 2 else "Remind me to go out with the garbage at 12:00"
    # Ensure DB exists
    init_db()
    asyncio.run(run_check(user_id, text))
