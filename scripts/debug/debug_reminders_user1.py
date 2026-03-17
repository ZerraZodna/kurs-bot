#!/usr/bin/env python3
import asyncio
import sys
from datetime import datetime, timezone
from pathlib import Path

# Ensure repo root is on path for src imports
repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.models.database import Memory, Schedule, SessionLocal, User, init_db
from src.services.dialogue_engine import DialogueEngine


def dump_user_state(db, user_id: int):
    print(f"\n{'=' * 80}")
({datetime.now(tz=timezone.utc).isoformat()})
    print(f"{'=' * 80}")

    user = db.query(User).filter_by(user_id=user_id).first()
    if not user:
        print("❌ User not found")
        return

    print(
        f"👤 User: id={user.user_id}, external_id={user.external_id}, name={user.first_name}, timezone={user.timezone}, current_lesson={user.lesson}"
    )

    print("\n📅 Schedules/Reminders:")
    schedules = db.query(Schedule).filter_by(user_id=user_id).order_by(Schedule.created_at.desc()).all()
    if not schedules:
        print("  (no schedules)")
    else:
        for s in schedules:
            status = "✅ ACTIVE" if s.is_active else "⏸️ INACTIVE"
            next_time = s.next_send_time.isoformat() if s.next_send_time else "None"
            lesson_title = s.lesson.title if s.lesson else "None"
            print(
                f"  {status} [{s.schedule_type}] id={s.schedule_id}, cron='{s.cron_expression}', next={next_time}, lesson='{lesson_title}'"
            )

    print("\n🧠 Relevant Memories (schedule-related, recent 50):")
    relevant_keys = ["schedule_message", "schedule_request_pending", "preferred_daily_time"]
    mems = (
        db
        .query(Memory)
        .filter(Memory.user_id == user_id, Memory.key.in_(relevant_keys))
        .order_by(Memory.created_at.desc())
        .limit(50)
        .all()
    )

    all_mems = db.query(Memory).filter_by(user_id=user_id).order_by(Memory.created_at.desc()).limit(20).all()
    if mems:
        for m in mems:
            preview = m.value[:150] + "..." if len(m.value) > 150 else m.value
            print(f"  [{m.category}] {m.key}: {preview}")
    elif all_mems:
        print("  (no schedule memories; recent general:)")
        for m in all_mems[:5]:
            preview = m.value[:100] + "..." if len(m.value) > 100 else m.value
            print(f"    [{m.category}] {m.key}: {preview}")
    else:
        print("  (no memories)")

    print(f"{'=' * 80}\n")


async def debug_reminders_query(user_id: int = 1, query: str = "What are my reminders"):
    """Debug the 'What are my reminders' query for a specific user."""
    db = SessionLocal()
    try:
        # Pre-query state
        dump_user_state(db, user_id)

        print(f"\n🚀 Invoking DialogueEngine.process_message(user_id={user_id}, text='{query}')")
        print("   (Live Ollama streaming ~20-40s)...\n")

        dialogue = DialogueEngine(db)
start_time = datetime.now(tz=timezone.utc)

        response = await dialogue.process_message(user_id, query, db)

        elapsed = datetime.now() - start_time
        print(f"⏱️  Initial process_message in {elapsed.total_seconds():.1f}s\n")

        full_response = ""
        diagnostics = None

        if isinstance(response, dict) and response.get("type") == "stream":
            print("📡 Streaming response detected - consuming generator & calling post_hook...\n")

            # Consume the stream (like telegram_stream.py)
            async for token in response["generator"]:
                full_response += token
                print(f"🔤 Token: {repr(token)}", end="", flush=True)
            print("\n📄 Full streamed response collected.\n")

            print(f"📝 Full response preview (len={len(full_response)}):")
            print(repr(full_response[:1000]) + ("..." if len(full_response) > 1000 else ""))
            print()

            # Call post_hook with full_response (executes functions!)
            print("🔧 Calling post_hook for function execution...\n")
            post_start = datetime.now()
            diagnostics = await response["post_hook"](full_response)
            post_elapsed = datetime.now() - post_start
            print(f"⏱️  post_hook completed in {post_elapsed.total_seconds():.1f}s\n")
        else:
            print("📄 Non-stream response:")
            print(response)
            full_response = str(response)

        # Print diagnostics from post_hook
        print("📊 Diagnostics (from post_hook):")
        print("-" * 60)
        if diagnostics:
            print(diagnostics)
            # Detailed breakdown
            print(f"\nstructured_intent_used: {diagnostics.get('structured_intent_used', 'N/A')}")
            print(f"dispatched_actions: {diagnostics.get('dispatched_actions', [])}")
            exec_result = diagnostics.get("execution_result")
            if exec_result and hasattr(exec_result, "results"):
                print("Functions executed:")
                for r in exec_result.results:
                    status = "✅" if r.success else "❌"
                    print(
                        f"  {status} {r.function_name}: {getattr(r, 'result', 'N/A') or getattr(r, 'error', 'no output')}"
                    )
                    if "get_user_schedules" in r.function_name or "schedule" in r.function_name.lower():
                        print("     🎯 REMINDER FUNCTION!")
            else:
                print("(no execution_result)")
        else:
            print("(no diagnostics returned)")
        print("-" * 60 + "\n")

        # Post-query state (functions should have run)
        print("\n🏁 Post-query state:")
        dump_user_state(db, user_id)

        print("\n✅ Debug complete! Check diagnostics for schedule functions (get_user_schedules etc.).")

    finally:
        db.close()


if __name__ == "__main__":
    # CLI: python -m scripts.debug.debug_reminders_user1 [user_id] [query]
    user_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    query = sys.argv[2] if len(sys.argv) > 2 else "What are my reminders"

    print(f"Debug script for user {user_id}: '{query}'")
    print("Initializing DB...\n")

    # Ensure DB tables exist
    init_db()

    asyncio.run(debug_reminders_query(user_id, query))
