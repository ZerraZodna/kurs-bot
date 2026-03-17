#!/usr/bin/env python3
import asyncio
import logging
import sys
from pathlib import Path

logging.basicConfig(level=logging.DEBUG)

repo_root = Path(__file__).resolve().parents[2]
if str(repo_root) not in sys.path:
    sys.path.insert(0, str(repo_root))

from src.integrations.telegram_stream import StreamingFilter
from src.models.database import SessionLocal, init_db
from src.services.dialogue_engine import DialogueEngine


async def test_cloud_lesson(user_id: int = 1, query: str = "send me todays lesson"):
    db = SessionLocal()
    try:
        dialogue = DialogueEngine(db)

        print(f"=== Testing '{query}' for user {user_id} ===")

        result = await dialogue.process_message(
            user_id=user_id,
            text=query,
            session=db,
            chat_id=123456,
            include_history=True,
            history_turns=4,
        )

        print("Result type:", result.get("type"))

        if result["type"] == "stream":
            print("Consuming raw generator...")
            raw_tokens = []
            async for token in result["generator"]:
                raw_tokens.append(token)
                print(f"RAW: {repr(token)}")

            full_raw = "".join(raw_tokens)
            print(f"\nFULL RAW RESPONSE (len={len(full_raw)}):")
            print(repr(full_raw))

            print("\nApplying StreamingFilter...")
            stream_filter = StreamingFilter(result["generator"])  # Note: generator already consumed

            # Simulate filter on full_raw
            filtered_stream = stream_filter.filter_stream()
            filtered_tokens = []
            async for token in filtered_stream:
                filtered_tokens.append(token)
                print(f"FILTERED: {repr(token)}")

            full_filtered = "".join(filtered_tokens)
            print(f"\nFULL FILTERED (len={len(full_filtered)}): {repr(full_filtered)}")

            remaining = stream_filter.get_remaining_for_functions()
            print(f"\nREMAINING FOR FUNCTIONS: {repr(remaining)}")

            print("\nCalling post_hook...")
            diagnostics = await result["post_hook"](full_raw)
            print("POST_HOOK DIAGNOSTICS:", diagnostics)

        else:
            print("Non-stream result:", result)
    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    asyncio.run(test_cloud_lesson())
