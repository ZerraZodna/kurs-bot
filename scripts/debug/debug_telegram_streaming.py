#!/usr/bin/env python3
import os
import sys
from pathlib import Path

# Ensure repo root is on path for src imports
repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

"""Test script for Telegram streaming path with function calling.


Simulates the exact Telegram streaming flow:
1. process_message_for_telegram() → streaming generator
2. StreamingFilter → clean tokens for Telegram  
3. Collect remaining_for_functions → post_hook for functions
4. Prints diagnostics for send_todays_lesson execution

Usage: python -m scripts.debug.debug_telegram_streaming [user_id] [text]
Defaults: user 1, "Send me todays lesson"

This invokes real Ollama (~30s).
"""

import asyncio
import sys
import time
from datetime import datetime
from typing import Optional

from src.models.database import SessionLocal, User, Memory, Schedule, init_db
from src.memories import MemoryManager  # Not directly used but for type hints if needed
from src.services.dialogue_engine import DialogueEngine
from src.integrations.telegram_stream import StreamingFilter


def dump_user_state(db, user_id: int):
    """Dump user state: user, schedules, recent memories."""
    print(f"\\n=== User {user_id} state (at {datetime.now().isoformat()}) ===")
    user = db.query(User).filter_by(user_id=user_id).first()
    if not user:
        print("❌ User not found")
        return
    
    print("User:", {
        "user_id": user.user_id, 
        "external_id": user.external_id, 
        "timezone": user.timezone, 
        "first_name": user.first_name, 
        "lesson": user.lesson
    })

    print("\\nSchedules:")
    schedules = db.query(Schedule).filter_by(user_id=user_id).all()
    for s in schedules:
        print(f"  - {s.schedule_id}: {s.schedule_type} cron={s.cron_expression} active={s.is_active} next={s.next_send_time}")

    print("\\nRecent memories (last 20):")
    mems = db.query(Memory).filter_by(user_id=user_id).order_by(Memory.created_at.desc()).limit(20).all()
    for m in mems:
        value_preview = m.value[:100] + '...' if len(m.value) > 100 else m.value
        print(f"  [{m.category}] {m.key}: {value_preview} (created {m.created_at})")
    
    print("=" * 80)


async def test_telegram_streaming(user_id: int, text: str):
    """Test full Telegram streaming + function calling path."""
    db = SessionLocal()
    try:
        # Dump initial state
        dump_user_state(db, user_id)
        
        print(f"\\n🚀 Testing: user={user_id} text='{text}'\\n")

        dialogue = DialogueEngine(db)
        
        start_time = time.time()
        
        # Step 1: Get streaming response (simulates telegram.py)
        result = await dialogue.process_message(
            user_id=user_id,
            text=text,
            session=db,
            chat_id=123456,  # Dummy chat_id
            include_history=True,
            history_turns=4,
        )
        
        elapsed = time.time() - start_time
        print(f"⏱️  process_message_for_telegram: {elapsed:.1f}s\\n")

        if result["type"] != "stream":
            print(f"❌ Expected streaming but got: {result.get('text', '??')[:200]}...")
            return

        print("✅ Streaming path OK\\n")

        # Step 2: Apply StreamingFilter (sim Telegram send_message_streaming)
        raw_generator = result["generator"]
        stream_filter = StreamingFilter(raw_generator)
        filtered_stream = stream_filter.filter_stream()
        
        print("📱 Simulating Telegram stream:")
        filtered_tokens = []
        async for token in filtered_stream:
            filtered_tokens.append(token)
            print(token)
        print("\\n📱 Stream complete\\n")

        full_response = ''.join(filtered_tokens)
        print(f"📄 Full Telegram response (len={len(full_response)}):\\n{repr(full_response[:1000])}...\\n")

        # Step 3: Extract for functions + post_hook (key Telegram step)
        remaining = stream_filter.get_remaining_for_functions()
        print(f"🔧 Remaining for functions (len={len(remaining) if remaining else 0}): {repr(remaining[:200]) if remaining else 'None'}\\n")

        function_text = remaining if remaining else full_response
        print(f"🔧 Running post_hook on: {repr(function_text[:200])}...\\n")

        # Step 4: Run post_hook for function execution
        diagnostics = await result["post_hook"](function_text)
        
        print("📊 Post-hook diagnostics:")
        print(f"  structured_intent_used: {diagnostics.get('structured_intent_used')}")
        print(f"  dispatched_actions: {diagnostics.get('dispatched_actions')}")
        
        execution_result = diagnostics.get('execution_result')
        if execution_result:
            print("✅ Functions executed!")
            for r in execution_result.results:
                status = "✅" if r.success else "❌"
                print(f"  {status} {r.function_name}: {r.result if r.result else r.error or 'no result'}")
                if r.function_name == "send_todays_lesson":
                    print(f"     🎉 TARGET FUNCTION HIT!")
        else:
            print("❌ No functions executed!")
        
        elapsed_total = time.time() - start_time
        print(f"⏱️  Total time: {elapsed_total:.1f}s\\n")

        # Dump final state
        print("\\n🏁 Final state:")
        dump_user_state(db, user_id)
        
    finally:
        db.close()


if __name__ == '__main__':
    if not sys.argv[1:]:
        print("Usage: python -m scripts.debug.debug_telegram_streaming [user_id] [\"text\"]")
        print('Example: python -m scripts.debug.debug_telegram_streaming 1 "Send me todays lesson"')
        sys.exit(1)
    
    user_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    text = sys.argv[2] if len(sys.argv) > 2 else "Send me todays lesson"
    
    # Init DB
    init_db()
    
    asyncio.run(test_telegram_streaming(user_id, text))

