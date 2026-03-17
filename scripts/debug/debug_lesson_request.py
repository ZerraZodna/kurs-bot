#!/usr/bin/env python3
import asyncio
import sys
from pathlib import Path

# Ensure repo root on path
repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.models.database import SessionLocal, User, init_db
from src.services.dialogue_engine import DialogueEngine


def dump_user_lesson_state(db, user_id: int):
    user = db.query(User).filter_by(user_id=user_id).first()
    if not user:
        print("User not found")
        return
    print(f"User {user_id}: lesson={user.lesson}")

async def test_lesson_request(user_id: int = 1, query: str = "send me todays lesson"):
    db = SessionLocal()
    try:
        dump_user_lesson_state(db, user_id)
        dialogue = DialogueEngine(db)
        response = await dialogue.process_message(user_id, query, db)
        
        full_response = ""
        if response.get("type") == "stream":
            async for token in response["generator"]:
                full_response += token
            diagnostics = await response["post_hook"](full_response)
            print("Full response:", full_response)
            print("Diagnostics:", diagnostics)
        else:
            print("Response:", response)
        
        dump_user_lesson_state(db, user_id)
    finally:
        db.close()

if __name__ == "__main__":
    user_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    query = sys.argv[2] if len(sys.argv) > 2 else "send me todays lesson"
    init_db()
    asyncio.run(test_lesson_request(user_id, query))

