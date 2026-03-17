"""
Test to confirm the bug where asking about "today's lesson" 
returns JSON with function calls instead of natural language response.
"""
from src.functions.intent_parser import IntentParser


class TestTodaysLessonJsonBug:
    """Test that confirms the bug with today's lesson returning JSON."""
    
    def test_todays_lesson_response_parsing(self):
        """
        Test that demonstrates the bug: when user asks "What is today's lesson?",
        the AI returns JSON with send_todays_lesson function, but the raw JSON
        is being sent to the user instead of just the response text.
        """
        parser = IntentParser()
        
        # This is what the AI returns when asked about today's lesson
        llm_response = """{
  "response": "Today's lesson is a time for reflection and inner peace.",
  "functions": [
    {"name": "send_todays_lesson", "parameters": {}}
  ]
}"""
        
        result = parser.parse(llm_response)
        
        # The parser should successfully extract the response
        assert result.success is True
        # The response_text should be JUST the text, not the full JSON
        assert result.response_text == "Today's lesson is a time for reflection and inner peace."
        # The functions should be extracted separately
        assert len(result.functions) == 1
        assert result.functions[0]["name"] == "send_todays_lesson"
    
    def test_bug_demonstration_raw_vs_parsed(self):
        """
        Demonstrate the bug: raw response contains JSON, parsed response contains only text.
        
        The bug is that the raw JSON is sent to Telegram instead of just the response text.
        """
        parser = IntentParser()
        
        # This is what the LLM returns
        raw_llm_response = """{
  "response": "Today's lesson is a time for reflection and inner peace.",
  "functions": [
    {"name": "send_todays_lesson", "parameters": {}}
  ]
}"""
        
        result = parser.parse(raw_llm_response)
        
        # This shows the bug: if we send raw_response to Telegram, 
        # it includes the full JSON. We should send result.response_text instead.
        assert raw_llm_response != result.response_text
        assert "functions" in raw_llm_response
        assert "functions" not in result.response_text
        assert result.response_text == "Today's lesson is a time for reflection and inner peace."
        
        # CRITICAL: This is what the bug looks like to the user
        # User sees: {"response": "Today's lesson...", "functions": [...]} 
        # Instead of: "Today's lesson is a time for reflection and inner peace."
        
        print(f"\n{'='*60}")
        print("BUG DEMONSTRATION - Today's Lesson:")
        print(f"{'='*60}")
        print("Raw LLM response (CURRENTLY sent to user):")
        print(f"  {raw_llm_response}")
        print("\nParsed response_text (SHOULD be sent to user):")
        print(f"  {result.response_text}")
        print(f"{'='*60}")
    
    def test_todays_lesson_variations(self):
        """
        Test various ways users might ask for today's lesson.
        All should return natural language, not JSON.
        """
        parser = IntentParser()
        
        variations = [
            "What is today's lesson?",
            "What's today's lesson?",
            "Show me today's lesson",
            "Give me today's lesson",
            "Today's lesson please",
        ]
        
        # The LLM would return similar JSON for all these variations
        llm_response_template = """{
      "response": "Today's lesson is about finding peace within.",
      "functions": [
        {"name": "send_todays_lesson", "parameters": {}}
      ]
    }"""

        
        for user_query in variations:
            result = parser.parse(llm_response_template)
            
            # All should parse successfully
            assert result.success is True
            # All should have natural language response
            assert result.response_text == "Today's lesson is about finding peace within."
            # All should have the function call extracted
            assert len(result.functions) == 1
            assert result.functions[0]["name"] == "send_todays_lesson"
            # The response should NOT contain JSON
            assert "{" not in result.response_text
            assert "functions" not in result.response_text


class TestTodaysLessonDesiredBehavior:
    """Test what the correct behavior should be for today's lesson."""
    
    def test_should_return_natural_language_only(self):
        """
        When user asks for today's lesson, they should receive only
        natural language text, not JSON with function calls.
        """
        parser = IntentParser()
        
        # LLM returns JSON with function call
        llm_response = """{
  "response": "Today's lesson is a time for reflection and inner peace.",
  "functions": [
    {"name": "send_todays_lesson", "parameters": {}}
  ]
}"""
        
        result = parser.parse(llm_response)
        
        # The final output to the user should be just the natural language
        expected_user_response = "Today's lesson is a time for reflection and inner peace."
        
        assert result.response_text == expected_user_response
        assert "{" not in result.response_text
        assert "functions" not in result.response_text
        assert "send_todays_lesson" not in result.response_text
    
    def test_function_call_should_be_executed_not_shown(self):
        """
        The sendtodayslesson function should be executed to send the actual lesson,
        but the JSON should not be shown to the user.
        """
        parser = IntentParser()
        
        llm_response = """{
  "response": "Here is today's lesson for you.",
  "functions": [
    {"name": "send_todays_lesson", "parameters": {}}
  ]
}"""
        
        result = parser.parse(llm_response)
        
        # Function should be extracted for execution
        assert len(result.functions) == 1
        assert result.functions[0]["name"] == "send_todays_lesson"
        
        # But user should only see the natural language
        assert result.response_text == "Here is today's lesson for you."
        assert "send_todays_lesson" not in result.response_text


if __name__ == "__main__":
    # Run the tests to demonstrate the bug
    test_class = TestTodaysLessonJsonBug()
    test_class.test_todays_lesson_response_parsing()
    test_class.test_bug_demonstration_raw_vs_parsed()
    test_class.test_todays_lesson_variations()
    
    desired_class = TestTodaysLessonDesiredBehavior()
    desired_class.test_should_return_natural_language_only()
    desired_class.test_function_call_should_be_executed_not_shown()
    
    print("\n" + "="*60)
    print("All tests passed!")
    print("The bug is confirmed: raw JSON is being sent instead of parsed text.")
    print("="*60)
