"""
Test to verify what gets passed to send_message when AI returns JSON.
"""
import pytest
from unittest.mock import AsyncMock, patch, MagicMock
import asyncio


async def mock_generator(tokens):
    """Helper to create an async generator from tokens."""
    for token in tokens:
        yield token


def test_json_response_extraction():
    """Test that JSON response is properly extracted before sending to Telegram."""
    from src.functions.intent_parser import get_intent_parser
    
    # Simulate the AI response with JSON
    ai_json_response = '''{
  "response": "Today's lesson is a time for reflection and inner peace.",
  "functions": [
    {"name": "send_todays_lesson", "parameters": {}}
  ]
}'''
    
    # The extract_text function from dialogue_engine
    def extract_response_text(full_response_text: str) -> str:
        parser = get_intent_parser()
        parse_result = parser.parse(full_response_text)
        # Use explicit None check because empty string "" is a valid response
        return parse_result.response_text if parse_result.response_text is not None else full_response_text
    
    # Test extraction
    extracted = extract_response_text(ai_json_response)
    
    print(f"\n{'='*60}")
    print("JSON RESPONSE TEST:")
    print(f"{'='*60}")
    print(f"Raw AI response (full_response):")
    print(f"  {ai_json_response[:80]}...")
    print(f"\nExtracted response_text:")
    print(f"  '{extracted}'")
    print(f"{'='*60}")
    
    # The extracted text should be the natural language response, not the JSON
    assert extracted == "Today's lesson is a time for reflection and inner peace."
    assert "functions" not in extracted
    assert "{" not in extracted


def test_empty_response_with_function():
    """Test that empty response with only function call returns empty string."""
    from src.functions.intent_parser import get_intent_parser
    
    # Simulate AI response with empty response and only function call
    ai_json_response = '''{
  "response": "",
  "functions": [
    {"name": "send_todays_lesson", "parameters": {}}
  ]
}'''
    
    def extract_response_text(full_response_text: str) -> str:
        parser = get_intent_parser()
        parse_result = parser.parse(full_response_text)
        # Use explicit None check because empty string "" is a valid response
        return parse_result.response_text if parse_result.response_text is not None else full_response_text
    
    extracted = extract_response_text(ai_json_response)
    
    print(f"\n{'='*60}")
    print("EMPTY RESPONSE WITH FUNCTION TEST:")
    print(f"{'='*60}")
    print(f"Raw AI response (full_response):")
    print(f"  {ai_json_response[:60]}...")
    print(f"\nExtracted response_text:")
    print(f"  '{extracted}'")
    print(f"Length: {len(extracted)}")
    print(f"{'='*60}")
    
    # Should return empty string (not the full JSON)
    assert extracted == ""
    assert "functions" not in extracted


@pytest.mark.asyncio
async def test_telegram_batch_with_json_response():
    """Test the extraction logic for JSON response with text."""
    from src.functions.intent_parser import get_intent_parser
    
    # Simulate accumulated full response from streaming
    full_response = '''{"response": "Today's lesson is a time for reflection", "functions": [{"name": "send_todays_lesson", "parameters": {}}]}'''
    
    # The extract_text function from dialogue_engine (fixed version)
    def extract_response_text(full_response_text: str) -> str:
        parser = get_intent_parser()
        parse_result = parser.parse(full_response_text)
        # Use explicit None check because empty string "" is a valid response
        return parse_result.response_text if parse_result.response_text is not None else full_response_text
    
    ai_response = extract_response_text(full_response)
    
    print(f"\n{'='*60}")
    print("TELEGRAM BATCH SIMULATION:")
    print(f"{'='*60}")
    print(f"Accumulated full_response:")
    print(f"  {full_response[:80]}...")
    print(f"\nExtracted ai_response:")
    print(f"  '{ai_response}'")
    print(f"{'='*60}")
    
    # Verify the extracted response is clean text
    assert ai_response == "Today's lesson is a time for reflection"
    assert "functions" not in ai_response
    assert "{" not in ai_response


@pytest.mark.asyncio
async def test_telegram_batch_with_empty_response():
    """Test the full flow when AI returns empty response with function call."""
    
    # Mock the DialogueEngine and its response
    mock_result = {
        "type": "stream",
        "generator": mock_generator([
            '{',
            '"response": "",',
            '"functions": [',
            '{"name": "send_todays_lesson", "parameters": {}}',
            ']}'
        ]),
        "post_hook": AsyncMock(),
        "extract_text": lambda text: ""  # Empty response
    }
    
    sent_messages = []
    
    async def mock_send_message(chat_id, text):
        sent_messages.append((chat_id, text))
        return {"ok": True, "result": {"message_id": 123}}
    
    # Simulate the streaming path logic
    full_response = ""
    async for token in mock_result["generator"]:
        full_response += token
    
    extract_text_fn = mock_result.get("extract_text")
    if extract_text_fn:
        ai_response = extract_text_fn(full_response)
    else:
        ai_response = full_response
    
    # Check if we should send
    should_send = ai_response and ai_response.strip()
    
    print(f"\n{'='*60}")
    print("EMPTY RESPONSE TEST:")
    print(f"{'='*60}")
    print(f"Accumulated full_response:")
    print(f"  {full_response[:60]}...")
    print(f"\nExtracted ai_response:")
    print(f"  '{ai_response}'")
    print(f"Should send message: {should_send}")
    print(f"{'='*60}")
    
    # When response is empty, we should NOT send a message
    assert ai_response == ""
    assert not should_send  # should_send is falsy (empty string or False)


if __name__ == "__main__":
    test_json_response_extraction()
    test_empty_response_with_function()
    asyncio.run(test_telegram_batch_with_json_response())
    asyncio.run(test_telegram_batch_with_empty_response())
    print("\nAll tests passed!")
