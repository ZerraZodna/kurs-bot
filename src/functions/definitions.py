"""
Function Definitions for Prompt Generation.

Generates prompt text describing available functions for the AI,
including JSON format instructions and examples.
"""

import json
import logging
from typing import Any, Dict, List, Optional

from .registry import FunctionRegistry, get_function_registry

logger = logging.getLogger(__name__)


class FunctionDefinitions:
    """Generates function definitions for AI prompts."""

    # Mapping from onboarding step values to granular context names
    ONBOARDING_STAGE_MAP = {
        "consent": "onboarding_consent",
    }

    # JSON format instructions template (compact)
    JSON_FORMAT_INSTRUCTIONS = """
Respond with valid JSON: {"response": "text", "functions": [{"name": "fn", "parameters": {}}]}
- "response": string (can be empty "")
- "functions": array (can be empty [])
- No markdown, no explanations
"""

    # Multi-function example (compact)
    MULTI_FUNCTION_EXAMPLE = """
Example - Lesson request:
{"response": "", "functions": [{"name": "send_todays_lesson", "parameters": {}}]}

Example - Reminders + lesson:
{"response": "I'll remind you throughout the day:", "functions": [
  {"name": "create_one_time_reminder", "parameters": {"run_at": "14:30", "message": "Lesson reminder"}},
  {"name": "create_one_time_reminder", "parameters": {"run_at": "17:00", "message": "Lesson reminder"}},
  {"name": "send_todays_lesson", "parameters": {}}
]}

For lesson requests: ALWAYS call send_todays_lesson, keep response empty.
"""

    # Context-specific examples (compact)
    CONTEXT_EXAMPLES = {
        "lesson_repeat": '{"response": "Great! Here\'s the lesson again.", "functions": [{"name": "confirm_yes", "parameters": {"context": "lesson_repeat"}}, {"name": "send_todays_lesson", "parameters": {}}]}',
        "onboarding_name": '{"response": "Nice to meet you, {name}!", "functions": [{"name": "extract_memory", "parameters": {"key": "first_name", "value": "{name}"}}]}',
        "onboarding_consent": '{"response": "Thank you!", "functions": [{"name": "confirm_yes", "parameters": {"context": "data_consent"}}]}',
        "schedule_setup": """Schedule: create_schedule(time="09:00"), delete_all_reminders()
Delete: delete_all_one_time_reminders(), delete_all_daily_reminders(), delete_all_reminders()
Query: query_schedule() to list before deleting""",
        "general_chat": """ALWAYS call set_current_lesson when user shares lesson progress:
- "I am on lesson 29" / "I'm on lesson 29" / "currently on lesson 29" → set_current_lesson(lesson_number=29)
- "My name is John" → extract_memory(key="first_name", value="John")
- "I'm in Oslo" / "I live in Norway" → set_timezone(timezone="Europe/Oslo")
Multiple facts in one message → multiple function calls""",
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
                is_valid, errors = self.registry.validate_call(func["name"], func["parameters"])
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
