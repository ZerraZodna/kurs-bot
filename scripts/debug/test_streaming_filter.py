"""Test script to verify streaming path with StreamingFilter."""

import asyncio
import sys

sys.path.insert(0, "/Users/johannessteen/kurs-bot")

from src.integrations.telegram_stream import StreamingFilter
from src.models.database import SessionLocal, init_db
from src.services.dialogue_engine import DialogueEngine


async def test_streaming_with_filter(user_id: int, text: str):
    """Test the streaming path that goes through StreamingFilter.

    This test simulates what telegram.py does:
    1. Get the streaming generator from process_message_for_telegram
    2. Pass it through StreamingFilter to clean up for Telegram display
    3. Get remaining_for_functions for function execution
    4. Call post_hook with the remaining content (includes functions JSON)
    """
    db = SessionLocal()
    try:
        dialogue = DialogueEngine(db)

        # Make ONE call to get the streaming response
        result = await dialogue.process_message_for_telegram(
            user_id=user_id,
            text=text,
            session=db,
            chat_id=123456,
            include_history=True,
            history_turns=4,
        )

        if result["type"] == "stream":
            print("✅ Streaming path activated!")

            # Get the raw generator and pass it through StreamingFilter
            raw_generator = result["generator"]
            stream_filter = StreamingFilter(raw_generator)
            filtered_stream = stream_filter.filter_stream()

            # Collect filtered tokens for Telegram display
            filtered_tokens = []
            async for token in filtered_stream:
                filtered_tokens.append(token)
                print(f"FILTERED: {repr(token[:1000])}")

            full_response = "".join(filtered_tokens)
            print(f"\n--- Full response for Telegram (length={len(full_response)}) ---")
            print(f"First 2000 chars: {repr(full_response[:2000])}")

            # Get remaining content for function processing
            # Pass full_response so we can extract functions from it
            remaining = stream_filter.get_remaining_for_functions()
            print("\n--- Remaining for functions ---")
            print(f"Remaining: {repr(remaining[:200] if remaining else None)}")

            # THE FIX: Use remaining_for_functions (includes functions JSON) for post_hook
            # This is what telegram.py does - it passes the functions to post_hook
            function_parse_text = remaining if remaining else full_response

            print("\n--- Running post_hook ---")
            print(f"Passing to post_hook (length={len(function_parse_text)}): {repr(function_parse_text[:200])}")

            diagnostics = await result["post_hook"](function_parse_text)

            print("\n--- Diagnostics ---")
            print(f"Keys: {diagnostics.keys() if diagnostics else 'None'}")
            print(f"structured_intent_used: {diagnostics.get('structured_intent_used')}")
            print(f"dispatched_actions: {diagnostics.get('dispatched_actions')}")
            print(f"execution_result: {diagnostics.get('execution_result')}")

            if diagnostics.get("execution_result"):
                print("\n✅ Function executed successfully!")
                results = diagnostics["execution_result"].results
                for r in results:
                    print(f"  - {r.function_name}: {r.success}")
                    if r.result:
                        print(f"    Result: {r.result}")
            else:
                print("\n❌ No function executed!")

        else:
            print(f"❌ Non-streaming response: {result['text'][:200]}...")

    finally:
        db.close()


if __name__ == "__main__":
    init_db()
    user_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    text = sys.argv[2] if len(sys.argv) > 2 else "Send me today´s lesson"
    asyncio.run(test_streaming_with_filter(user_id, text))
