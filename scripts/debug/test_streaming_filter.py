"""Test script to verify streaming path with StreamingFilter."""
import asyncio
import sys
sys.path.insert(0, '/Users/johannessteen/kurs-bot')

from src.models.database import SessionLocal, init_db
from src.services.dialogue_engine import DialogueEngine
from src.integrations.telegram_stream import StreamingFilter


async def test_streaming_with_filter(user_id: int, text: str):
    """Test the streaming path that goes through StreamingFilter."""
    db = SessionLocal()
    try:
        dialogue = DialogueEngine(db)
        
        # Use process_message_for_telegram which returns streaming context
        result = await dialogue.process_message_for_telegram(
            user_id=user_id,
            text=text,
            session=db,
            chat_id=123456,  # Dummy chat_id for testing
            include_history=True,
            history_turns=4,
        )
        
        if result["type"] == "stream":
            print("✅ Streaming path activated!")
            print("\n--- Raw tokens from Ollama (before filter) ---")
            
            raw_tokens = []
            async for token in result["generator"]:
                raw_tokens.append(token)
                print(f"RAW: {repr(token[:100])}")
            
            print(f"\n--- Total raw tokens: {len(raw_tokens)} ---")
            print(f"--- Raw response length: {len(''.join(raw_tokens))} ---")
            
            # Now test the StreamingFilter
            print("\n--- Testing StreamingFilter ---")
            
            # Re-create generator for filter test
            result2 = await dialogue.process_message_for_telegram(
                user_id=user_id,
                text=text,
                session=db,
                chat_id=123456,
                include_history=True,
                history_turns=4,
            )
            
            if result2["type"] == "stream":
                raw_generator = result2["generator"]
                stream_filter = StreamingFilter(raw_generator)
                filtered_stream = stream_filter.filter_stream()
                
                filtered_tokens = []
                async for token in filtered_stream:
                    filtered_tokens.append(token)
                    print(f"FILTERED: {repr(token[:100])}")
                
                print(f"\n--- Total filtered tokens: {len(filtered_tokens)} ---")
                print(f"--- Filtered response length: {len(''.join(filtered_tokens))} ---")
                
                # Get remaining content for functions
                remaining = stream_filter.get_remaining_for_functions()
                print(f"\n--- Remaining for functions: {repr(remaining[:200] if remaining else None)} ---")
                
                # Run post_hook
                full_response = ''.join(filtered_tokens)
                print("\n--- Running post_hook (trigger matching) ---")
                diagnostics = await result2["post_hook"](full_response)
                print(f"Diagnostics keys: {diagnostics.keys() if diagnostics else 'None'}")
                
        else:
            print(f"❌ Non-streaming response: {result['text'][:200]}...")
            
    finally:
        db.close()


if __name__ == '__main__':
    init_db()
    user_id = int(sys.argv[1]) if len(sys.argv) > 1 else 1
    text = sys.argv[2] if len(sys.argv) > 2 else "Please explain"
    asyncio.run(test_streaming_with_filter(user_id, text))

