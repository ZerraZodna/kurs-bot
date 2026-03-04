#!/usr/bin/env python3
"""Test the JSON extractor with the specific problematic JSON."""

import json
from src.functions.intent_parser import get_intent_parser

# The exact JSON that was showing in the web UI
test_json = """{

  "response": "I understand your preference, Johannes. You can set your lesson preference to 'always_next' to move forward without daily reminders. Would you like me to set that for you?",

  "functions": [

    {"name": "set_lesson_preference", "parameters": {"preference": "always_next", "skip_confirmation": "true"}}

  ]

}"""

def test_intent_parser():
    """Test that the intent parser correctly extracts the response text."""
    parser = get_intent_parser()
    result = parser.parse(test_json)
    
    print("Parse Result:")
    print(f"  success: {result.success}")
    print(f"  response_text: {result.response_text!r}")
    print(f"  functions: {result.functions}")
    print(f"  errors: {result.errors}")
    print(f"  is_fallback: {result.is_fallback}")
    
    # The response text should be the natural language, not the raw JSON
    expected_response = "I understand your preference, Johannes. You can set your lesson preference to 'always_next' to move forward without daily reminders. Would you like me to set that for you?"
    
    if result.response_text == expected_response:
        print("\n✅ PASS: Response text correctly extracted")
        return True
    else:
        print(f"\n❌ FAIL: Expected response text to be:")
        print(f"   {expected_response!r}")
        print(f"   But got:")
        print(f"   {result.response_text!r}")
        return False

if __name__ == "__main__":
    success = test_intent_parser()
    exit(0 if success else 1)
