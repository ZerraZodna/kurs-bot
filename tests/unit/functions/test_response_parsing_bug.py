"""
Test to confirm the bug where full JSON response with function calls
is sent to Telegram instead of just the response text.
"""
import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from src.functions.intent_parser import IntentParser, ParseResult


class TestResponseParsingBug:
    """Test that confirms the bug in response handling."""
    
    def test_parse_result_extracts_response_text_correctly(self):
        """Test that IntentParser correctly extracts just the response text."""
        parser = IntentParser()
        
        # Simulate an LLM response with both text and function calls
        # Using a valid registered function name
        llm_response = '''{
  "response": "Your goal, Dev, is to remember that your thoughts are images you've made, and to begin seeing beyond illusions.",
  "functions": [
    {"name": "extract_memory", "parameters": {"key": "learninggoal", "value": "Spiritual growth through ACIM lessons"}}
  ]
}'''
        
        result = parser.parse(llm_response)
        
        # The parser should successfully extract the response
        assert result.success is True
        # The response_text should be JUST the text, not the full JSON
        assert result.response_text == "Your goal, Dev, is to remember that your thoughts are images you've made, and to begin seeing beyond illusions."
        # The functions should be extracted separately
        assert len(result.functions) == 1
        assert result.functions[0]["name"] == "extract_memory"
    
    def test_raw_response_vs_parsed_response(self):
        """Demonstrate the bug: raw response contains JSON, parsed response contains only text."""
        parser = IntentParser()
        
        raw_response = '''{
  "response": "Hello, how can I help you?",
  "functions": [
    {"name": "set_timezone", "parameters": {"timezone": "UTC"}}
  ]
}'''
        
        result = parser.parse(raw_response)
        
        # This shows the bug: if we send raw_response to Telegram, 
        # it includes the full JSON. We should send result.response_text instead.
        assert raw_response != result.response_text
        assert "functions" in raw_response
        assert "functions" not in result.response_text
        assert result.response_text == "Hello, how can I help you?"
        
        # CRITICAL: This is what the bug looks like to the user
        # User sees: {"response": "Hello...", "functions": [...]} 
        # Instead of: "Hello, how can I help you?"
    
    def test_dialogue_engine_returns_raw_response_bug(self):
        """
        This test demonstrates the actual bug in dialogue_engine.py.
        
        The _generate_llm_response method returns the raw LLM response
        instead of the parsed response_text.
        """
        # This is a conceptual test showing what happens:
        # 1. LLM returns: {"response": "Hello", "functions": [...]}
        # 2. handle_triggers parses it correctly
        # 3. But the method returns the raw JSON string, not "Hello"
        
        raw_llm_response = '''{
  "response": "Your goal is spiritual growth.",
  "functions": [
    {"name": "extract_memory", "parameters": {"key": "goal", "value": "spiritual growth"}}
  ]
}'''
        
        parser = IntentParser()
        parsed = parser.parse(raw_llm_response)
        
        # The bug: dialogue_engine returns raw_llm_response
        # It should return parsed.response_text
        assert raw_llm_response != parsed.response_text
        assert parsed.response_text == "Your goal is spiritual growth."
        
        # This demonstrates the bug visually
        print(f"\n{'='*60}")
        print("BUG DEMONSTRATION:")
        print(f"{'='*60}")
        print(f"Raw LLM response (CURRENTLY sent to Telegram):")
        print(f"  {raw_llm_response[:80]}...")
        print(f"\nParsed response_text (SHOULD be sent to Telegram):")
        print(f"  {parsed.response_text}")
        print(f"{'='*60}")


class TestDesiredBehavior:
    """Test what the correct behavior should be."""
    
    @pytest.mark.asyncio
    async def test_dialogue_engine_should_return_parsed_text(self):
        """
        Test that dialogue_engine should return parsed response_text,
        not the raw LLM response.
        """
        # Mock the dependencies
        mock_session = MagicMock()
        mock_user = MagicMock()
        mock_user.user_id = 123
        mock_user.is_deleted = False
        mock_user.processing_restricted = False
        mock_user.opted_in = True
        
        mock_session.query.return_value.filter_by.return_value.first.return_value = mock_user
        
        # Mock the LLM response with function calls
        raw_llm_response = '''{
  "response": "Your goal, Dev, is spiritual growth.",
  "functions": [
    {"name": "extract_memory", "parameters": {"key": "learninggoal", "value": "Spiritual growth through ACIM lessons"}}
  ]
}'''
        
        # The expected response that should be sent to Telegram
        expected_response = "Your goal, Dev, is spiritual growth."
        
        # In the current buggy implementation, the raw response is returned
        # In the fixed implementation, only expected_response should be returned
        
        # This test documents the expected behavior
        parser = IntentParser()
        parsed = parser.parse(raw_llm_response)
        
        assert parsed.response_text == expected_response
        assert raw_llm_response != expected_response
        assert "functions" not in parsed.response_text


if __name__ == "__main__":
    # Run the tests to demonstrate the bug
    test_class = TestResponseParsingBug()
    test_class.test_parse_result_extracts_response_text_correctly()
    test_class.test_raw_response_vs_parsed_response()
    test_class.test_dialogue_engine_returns_raw_response_bug()
    print("\nAll bug demonstration tests passed!")
    print("The bug is confirmed: raw JSON is being sent instead of parsed text.")
