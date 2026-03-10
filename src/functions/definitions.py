"""
Function Definitions for Prompt Generation.

Generates prompt text describing available functions for the AI,
including JSON format instructions and examples.
"""

from typing import Dict, List, Optional, Any
import json
import logging
from .registry import FunctionRegistry, get_function_registry

logger = logging.getLogger(__name__)


class FunctionDefinitions:
    """Generates function definitions for AI prompts."""
    
    # Mapping from onboarding step values to granular context names
    ONBOARDING_STAGE_MAP = {
        "consent": "onboarding_consent",
    }
    
    # JSON format instructions template
    JSON_FORMAT_INSTRUCTIONS = """
You must ALWAYS respond with valid JSON in the following format:

{
  "response": "Your natural language response to the user (can be empty string if only functions needed)",
  "functions": [
    {
      "name": "function_name",
      "parameters": {
        "param1": "value1",
        "param2": "value2"
      }
    }
  ]
}

Rules:
1. The "response" field is required - it contains text the user will see
2. The "functions" array contains actions to execute (can be empty [])
3. Only use functions listed under "Available Functions" for the current context
4. All required parameters must be included
5. Use exact function names and parameter names as shown
6. Return ONLY the JSON, no explanations outside the JSON

CRITICAL MEMORY EXTRACTION RULE:
When the user shares personal information (name, timezone, current lesson, preferences, etc.), you MUST call extract_memory to store it. NEVER just acknowledge the information in text - always extract and store it using the extract_memory function.

Examples of when to use extract_memory:
- User says "My name is John" → call extract_memory with key="first_name", value="John"
- User says "I'm on lesson 25" → call extract_memory with key="current_lesson", value="25"
- User says "Call me Sarah" → call extract_memory with key="first_name", value="Sarah"
- User says "I'm in Tokyo" → call extract_memory with key="timezone", value="Asia/Tokyo"
"""
    
    # Multi-function example
    MULTI_FUNCTION_EXAMPLE = """
Example - User asks for today's lesson:
User: "what is todays lesson?"

{
  "response": "",
  "functions": [
    {"name": "send_todays_lesson", "parameters": {}}
  ]
}

Example - User asks for the full lesson text:
User: "what is the text?"

{
  "response": "",
  "functions": [
    {"name": "send_todays_lesson", "parameters": {}}
  ]
}

Example - User asks for all the text:
User: "all the text?"

{
  "response": "",
  "functions": [
    {"name": "send_todays_lesson", "parameters": {}}
  ]
}

Example - Multiple reminders + lesson:
User: "Remind me about today's thru the day"

{
  "response": "I'll remind you about today's lesson every 30 minutes. Here are the reminders:",
  "functions": [
    {"name": "create_one_time_reminder", "parameters": {"run_at": "2024-01-15T12:30:00", "message": "Lesson reminder"}},
    {"name": "create_one_time_reminder", "parameters": {"run_at": "2024-01-15T15:00:00", "message": "Lesson reminder"}},
    {"name": "create_one_time_reminder", "parameters": {"run_at": "2024-01-15T17:30:00", "message": "Lesson reminder"}},
    {"name": "send_todays_lesson", "parameters": {}}
  ]
}

CRITICAL: When the user asks for "today's lesson", "the text", "all the text", "full text", or "entire lesson", you MUST:
1. ALWAYS call send_todays_lesson function
2. ALWAYS set the response field to an empty string: "response": ""
3. NEVER write any text in the response field - no introductions, no summaries, no descriptions
4. The system will automatically display the full lesson content from the function result

If you write any text in the response field, the user will see duplicate or partial content. Keep response EMPTY.

Important: When creating multiple reminders:
1. Calculate times starting from the current time (e.g., if current time is 14:15, first reminder at 14:30)
2. Never create duplicate reminders at the same time - each reminder must have a unique timestamp
"""
    
    # Context-specific examples
    CONTEXT_EXAMPLES = { 
        "lesson_repeat": """
Example - User says "Yes, repeat" after being offered a repeat lesson:
User: "Yes, repeat"

{
  "response": "Perfect! Here's Lesson {lesson_id} again.",
  "functions": [
    {"name": "confirm_yes", "parameters": {"context": "lesson_repeat"}},
    {"name": "send_todays_lesson", "parameters": {"lesson_id": "{lesson_id}"}}
  ]
}

Example - User says "yes" to repeat:
User: "yes"

{
  "response": "Great! Sending you the lesson again.",
  "functions": [
    {"name": "confirm_yes", "parameters": {"context": "lesson_repeat"}},
    {"name": "send_todays_lesson", "parameters": {}}
  ]
}
""",
        "onboarding_name": """
Example - User confirms using Telegram name:
User: "yes"

{
  "response": "Great! I'll use your name from Telegram.",
  "functions": [
    {"name": "confirm_yes", "parameters": {"context": "use_telegram_name"}}
  ]
}

Example - User declines using Telegram name:
User: "no"

{
  "response": "No problem! What would you like me to call you?",
  "functions": [
    {"name": "confirm_no", "parameters": {"context": "use_telegram_name"}}
  ]
}

Example - Extracting name from complex sentence:
User: "My name is Johannes. Got that?"

{
  "response": "Nice to meet you, Johannes! I've noted your name.",
  "functions": [
    {"name": "extract_memory", "parameters": {"key": "first_name", "value": "Johannes", "confidence": 0.9}}
  ]
}

Example - Remembering name:
User: "Remember my name is Sarah"

{
  "response": "Nice to meet you, Sarah! I've noted your name.",
  "functions": [
    {"name": "extract_memory", "parameters": {"key": "name", "value": "Sarah", "confidence": 0.95}}
  ]
}
""",
        "onboarding_consent": """
Example - User grants consent:
User: "yes, I agree"

{
  "response": "Thank you! Your consent has been recorded. Let's continue with your setup.",
  "functions": [
    {"name": "confirm_yes", "parameters": {"context": "data_consent"}}
  ]
}

Example - User declines consent:
User: "no, I don't want that"

{
  "response": "I understand. Without consent to store your data, I cannot provide personalized service. Your information will be deleted.",
  "functions": [
    {"name": "confirm_no", "parameters": {"context": "data_consent"}}
  ]
}
""",
        "schedule_setup": """
Example - Creating schedule:
User: "Remind me every day at 9am"

{
  "response": "Perfect! I've set up a daily reminder at 9:00 AM. You'll receive your ACIM lesson at this time every day.",
  "functions": [
    {"name": "create_schedule", "parameters": {"time": "09:00", "message": "Time for your daily ACIM lesson"}},
    {"name": "set_preferred_time", "parameters": {"time": "09:00"}},
    {"name": "extract_memory", "parameters": {"key": "preferred_time", "value": "09:00", "confidence": 0.9}}
  ]
}

Example - Deleting one-time reminder:
User: "Delete my one time reminder"

{
  "response": "I'll help you delete your one-time reminder. Let me first check what reminders you have.",
  "functions": [
    {"name": "query_schedule", "parameters": {}}
  ]
}

Then after seeing the schedule list with schedule_id, the AI should call:
{
  "response": "One-time reminder deleted.",
  "functions": [
    {"name": "delete_one_time_reminder", "parameters": {"schedule_id": 123}}
  ]
}

Example - Deleting all one-time reminders:
User: "Delete all my one time reminders"

{
  "response": "All one-time reminders have been deleted.",
  "functions": [
    {"name": "delete_all_one_time_reminders", "parameters": {}}
  ]
}

Example - Deleting all daily reminders:
User: "Delete my daily reminders"

{
  "response": "All daily reminders have been deleted.",
  "functions": [
    {"name": "delete_all_daily_reminders", "parameters": {}}
  ]
}

Example - Deleting all reminders:
User: "Delete all my reminders"

{
  "response": "All reminders have been deleted. You won't receive any more scheduled messages unless you set new reminders.",
  "functions": [
    {"name": "delete_all_reminders", "parameters": {}}
  ]
}
""",
        "general_chat": """
Example - Extracting current lesson:
User: "I'm on lesson 25 now"

{
  "response": "Great progress! I've noted that you're on lesson 25.",
  "functions": [
    {"name": "extract_memory", "parameters": {"key": "current_lesson", "value": "25", "confidence": 0.85}}
  ]
}

Example - Multiple extractions with timezone:
User: "My name is John and I'm in Tokyo, studying lesson 30"

{
  "response": "Thanks John! I've noted your details and set your timezone.",
  "functions": [
    {"name": "extract_memory", "parameters": {"key": "name", "value": "John", "confidence": 0.9}},
    {"name": "set_timezone", "parameters": {"timezone": "Asia/Tokyo"}},
    {"name": "extract_memory", "parameters": {"key": "current_lesson", "value": "30", "confidence": 0.8}}
  ]
}
""",
    }
    
    def __init__(self, registry: Optional[FunctionRegistry] = None):
        self.registry = registry or get_function_registry()
    
    def for_context(self, context: str) -> str:
        """Generate function definitions for a specific context."""
        # Map granular onboarding contexts to the base "onboarding" for function filtering
        # while using stage-specific examples
        function_context = context
        if context.startswith("onboarding_"):
            function_context = "onboarding"
        
        functions = self.registry.list_for_context(function_context)
        
        lines = [
            "-- Available Functions",
            "",
            "You can call these functions to perform actions:",
            "",
        ]
        
        for func in functions:
            lines.append(func.to_prompt_text())
            lines.append("")
        
        # Add JSON format instructions
        lines.extend([
            "",
            self.JSON_FORMAT_INSTRUCTIONS,
            "",
        ])
        
        # Add context-specific example if available
        # Check for exact match first (including granular onboarding stages)
        if context in self.CONTEXT_EXAMPLES:
            lines.append("-- Examples for this context")
            lines.append(self.CONTEXT_EXAMPLES[context])
        else:
            lines.append(self.MULTI_FUNCTION_EXAMPLE)
        
        return "\n".join(lines)
    
    def for_functions(self, function_names: List[str]) -> str:
        """Generate definitions for specific functions."""
        lines = [
            "-- Available Functions",
            "",
            "You can call these functions to perform actions:",
            "",
        ]
        
        for name in function_names:
            func = self.registry.get(name)
            if func:
                lines.append(func.to_prompt_text())
                lines.append("")
        
        lines.extend([
            "",
            self.JSON_FORMAT_INSTRUCTIONS,
            "",
            self.MULTI_FUNCTION_EXAMPLE,
        ])
        
        return "\n".join(lines)
    
    def all_functions(self) -> str:
        """Generate definitions for all functions."""
        return self.for_context("general_chat")
    
    def build_system_prompt(
        self,
        base_prompt: str,
        context: str = "general_chat",
        include_functions: bool = True,
    ) -> str:
        """Build a complete system prompt with function definitions."""
        if not include_functions:
            return base_prompt
        
        function_defs = self.for_context(context)
        
        return f"""{base_prompt}

{function_defs}

Remember: Always return valid JSON with "response" and "functions" fields."""
    
    def get_function_example(self, function_name: str) -> Optional[Dict[str, Any]]:
        """Get an example call for a specific function."""
        func = self.registry.get(function_name)
        if not func or not func.examples:
            return None
        
        return {
            "name": function_name,
            "parameters": func.examples[0],
        }
    
    def validate_response_format(self, response_text: str) -> tuple[bool, Optional[str]]:
        """Validate that a response follows the expected JSON format."""
        try:
            data = json.loads(response_text)
            
            # Check required fields
            if "response" not in data:
                return False, "Missing 'response' field"
            
            if "functions" not in data:
                return False, "Missing 'functions' field"
            
            if not isinstance(data["functions"], list):
                return False, "'functions' must be an array"
            
            # Validate each function call
            for i, func in enumerate(data["functions"]):
                if not isinstance(func, dict):
                    return False, f"Function {i} must be an object"
                
                if "name" not in func:
                    return False, f"Function {i} missing 'name'"
                
                if "parameters" not in func:
                    return False, f"Function {i} missing 'parameters'"
                
                if not isinstance(func["parameters"], dict):
                    return False, f"Function {i} 'parameters' must be an object"
                
                # Validate function exists
                if not self.registry.is_valid_function(func["name"]):
                    return False, f"Unknown function: {func['name']}"
                
                # Validate parameters
                is_valid, errors = self.registry.validate_call(
                    func["name"], func["parameters"]
                )
                if not is_valid:
                    return False, f"Function {func['name']}: {', '.join(errors)}"
            
            return True, None
            
        except json.JSONDecodeError as e:
            return False, f"Invalid JSON: {str(e)}"
        except Exception as e:
            return False, f"Validation error: {str(e)}"


# Global instance
_definitions: Optional[FunctionDefinitions] = None


def get_function_definitions(registry: Optional[FunctionRegistry] = None) -> FunctionDefinitions:
    """Get the global function definitions instance."""
    global _definitions
    if _definitions is None:
        _definitions = FunctionDefinitions(registry)
    return _definitions


def reset_definitions():
    """Reset the global instance (useful for testing)."""
    global _definitions
    _definitions = None
