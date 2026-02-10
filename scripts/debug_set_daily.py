import asyncio
import json
import sys
from datetime import datetime

from src.models.database import SessionLocal, User, Memory, Schedule, init_db
from src.services.memory_manager import MemoryManager
from src.services.dialogue_engine import DialogueEngine


def dump_user_state(db, user_id):
    print(f"\n=== Inspecting user {user_id} state ===")
    user = db.query(User).filter_by(user_id=user_id).first()
    if not user:
        print("User not found")
        return
    print("User:", {"user_id": user.user_id, "external_id": user.external_id, "timezone": user.timezone, "first_name": user.first_name})

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
        v = m.value
        if v is None:
            v = ""
        print({"key": m.key, "category": m.category, "value": (v[:200] + '...' if len(v) > 200 else v), "created_at": (m.created_at.isoformat() if m.created_at else None)})


async def run_check(user_id: int, text: str):
    db = SessionLocal()
    try:
        dump_user_state(db, user_id)

        print("\nInvoking DialogueEngine.process_message() with text:\n", text)
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
    text = sys.argv[2] if len(sys.argv) > 2 else "Set my daily reminder for lessons to 09:00"
    # Ensure DB exists
    init_db()
    asyncio.run(run_check(user_id, text))
