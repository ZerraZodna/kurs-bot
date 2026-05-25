"""
Critical path tests for function calling infrastructure.
Tests key functions without requiring full database setup.
"""

import json
from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from src.functions.executor import BatchExecutionResult, ExecutionResult, FunctionExecutor
from src.functions.intent_parser import IntentParser, get_intent_parser
from src.functions.parameters import ParameterValidator

# Import the modules we're testing
from src.functions.registry import FunctionRegistry, get_function_registry
from src.functions.response_builder import ResponseBuilder


class TestFunctionRegistry:
    """Test function registry operations."""

    def test_all_functions_registered(self):
        """Verify all 17+ functions are registered."""
        registry = FunctionRegistry()
        all_functions = registry.list_all()

        expected_functions = [
            "create_schedule",
            "update_schedule",
            "delete_schedule",
            "query_schedule",
            "create_one_time_reminder",
            "send_lesson",
            "send_todays_lesson",
            "set_timezone",
            "set_language",
            "set_preferred_time",
            "update_profile",
            "confirm_yes",
            "confirm_no",
            "extract_memory",
        ]

        registered_names = [f.name for f in all_functions]

        for func_name in expected_functions:
            assert func_name in registered_names, f"Function {func_name} not registered"

        assert len(all_functions) >= 17, f"Expected at least 17 functions, got {len(all_functions)}"

    def test_extract_memory_function_exists(self):
        """Verify extract_memory function is properly configured."""
        registry = FunctionRegistry()
        func = registry.get("extract_memory")

        assert func is not None
        assert func.name == "extract_memory"
        assert "general_chat" in func.contexts
        assert "onboarding" in func.contexts

        # Check parameters
        param_names = [p.name for p in func.parameters]
        assert "key" in param_names
        assert "value" in param_names
        assert "ttl_hours" in param_names

    def test_context_filtering(self):
        """Test that functions are filtered by context."""
        registry = FunctionRegistry()

        general_functions = registry.list_for_context("general_chat")
        onboarding_functions = registry.list_for_context("onboarding")
        schedule_functions = registry.list_for_context("schedule_setup")

        # General chat should have most functions
        assert len(general_functions) >= 15

        # Onboarding should have timezone, language, profile functions
        onboarding_names = [f.name for f in onboarding_functions]
        assert "set_timezone" in onboarding_names
        assert "set_language" in onboarding_names
        assert "extract_memory" in onboarding_names

        # Schedule setup should have scheduling functions
        schedule_names = [f.name for f in schedule_functions]
        assert "create_schedule" in schedule_names
        assert "query_schedule" in schedule_names


class TestIntentParser:
    """Test intent parsing from LLM responses."""

    def test_parse_valid_json_response(self):
        """Test parsing a valid JSON response with functions."""
        parser = IntentParser()

        response = json.dumps({
            "response": "I'll set up your schedule for 9:00 AM.",
            "functions": [
                {"name": "create_schedule", "parameters": {"time": "09:00"}},
                {"name": "extract_memory", "parameters": {"key": "preferred_lesson_time", "value": "09:00"}},
            ],
        })

        result = parser.parse(response)

        assert result.success is True
        assert result.response_text == "I'll set up your schedule for 9:00 AM."
        assert len(result.functions) == 2
        assert result.functions[0]["name"] == "create_schedule"
        assert result.functions[1]["name"] == "extract_memory"

    def test_parse_json_with_markdown_code_blocks(self):
        """Test parsing JSON wrapped in markdown code blocks."""
        parser = IntentParser()

        response = """```json
{
  "response": "Got it!",
  "functions": [{"name": "confirm_yes", "parameters": {}}]
}
```"""

        result = parser.parse(response)

        assert result.success is True
        assert result.response_text == "Got it!"
        assert len(result.functions) == 1

    def test_parse_fallback_to_text(self):
        """Test that non-JSON responses are treated as natural language."""
        parser = IntentParser()

        response = "This is just a natural language response without any JSON."

        result = parser.parse(response)

        assert result.success is True  # Still success - we have text to show
        assert result.is_fallback is True
        assert result.response_text == response
        assert len(result.functions) == 0

    def test_parse_extract_memory_current_lesson_json(self):
        """Test parsing provided JSON payload with extract_memory for current lesson."""
        parser = IntentParser()

        response = json.dumps({
            "response": "Thank you for letting me know, Dev. I honor your journey as you continue with lesson 23.",
            "functions": [{"name": "extract_memory", "parameters": {"key": "current_lesson", "value": "23"}}],
        })

        result = parser.parse(response)

        assert result.success is True
        assert (
            result.response_text
            == "Thank you for letting me know, Dev. I honor your journey as you continue with lesson 23."
        )
        assert len(result.functions) == 1
        assert result.functions[0]["name"] == "extract_memory"
        assert result.functions[0]["parameters"]["key"] == "current_lesson"
        assert result.functions[0]["parameters"]["value"] == "23"

    def test_parse_invalid_function_name(self):
        """Test validation of unknown function names."""
        parser = IntentParser()

        response = json.dumps({"response": "Testing", "functions": [{"name": "unknown_function", "parameters": {}}]})

        result = parser.parse(response)

        assert result.success is False
        assert len(result.errors) > 0
        assert any("Unknown function" in e for e in result.errors)


class TestParameterValidator:
    """Test parameter validation and coercion."""

    def test_validate_time_formats(self):
        """Test various time format validations."""
        validator = ParameterValidator()

        # Valid formats
        valid_cases = [
            ("09:00", "09:00"),
            ("9:00", "09:00"),
            ("14:30", "14:30"),
            ("9am", "09:00"),
            ("9:00am", "09:00"),
            ("9 AM", "09:00"),
            ("2:30pm", "14:30"),
        ]

        for input_time, expected in valid_cases:
            is_valid, normalized, error = validator.validate_time(input_time)
            assert is_valid, f"Expected {input_time} to be valid, got error: {error}"
            assert normalized == expected, f"Expected {expected}, got {normalized}"

    def test_validate_time_invalid(self):
        """Test invalid time formats are rejected."""
        validator = ParameterValidator()

        invalid_cases = ["25:00", "09:70", "not-a-time", "", "9:99"]

        for input_time in invalid_cases:
            is_valid, normalized, error = validator.validate_time(input_time)
            assert not is_valid, f"Expected {input_time} to be invalid"
            assert error is not None

    def test_validate_timezone(self):
        """Test timezone validation and normalization."""
        validator = ParameterValidator()

        # Valid timezones
        valid_cases = [
            ("Europe/Oslo", "Europe/Oslo"),
            ("oslo", "Europe/Oslo"),
            ("New York", "America/New_York"),
            ("Tokyo", "Asia/Tokyo"),
            ("Asia/Tokyo", "Asia/Tokyo"),
        ]

        for input_tz, expected in valid_cases:
            is_valid, normalized, error = validator.validate_timezone(input_tz)
            assert is_valid, f"Expected {input_tz} to be valid, got error: {error}"
            assert normalized == expected, f"Expected {expected}, got {normalized}"

    def test_validate_language(self):
        """Test language code validation."""
        validator = ParameterValidator()

        valid_cases = [
            ("en", "en"),
            ("English", "en"),
            ("no", "no"),
            ("norsk", "no"),
            ("es", "es"),
            ("Spanish", "es"),
        ]

        for input_lang, expected in valid_cases:
            is_valid, normalized, error = validator.validate_language(input_lang)
            assert is_valid, f"Expected {input_lang} to be valid, got error: {error}"
            assert normalized == expected, f"Expected {expected}, got {normalized}"

    def test_validate_datetime(self):
        """Test datetime validation."""
        validator = ParameterValidator()

        valid_cases = [
            "2024-01-15T09:00:00",
            "2024-01-15 09:00:00",
            "2024-01-15T09:00",
            "2024-01-15",
        ]

        for input_dt in valid_cases:
            is_valid, dt_obj, error = validator.validate_datetime(input_dt)
            assert is_valid, f"Expected {input_dt} to be valid, got error: {error}"
            assert isinstance(dt_obj, datetime)


class TestFunctionExecutor:
    """Test function execution."""

    @pytest.mark.asyncio
    async def test_execute_single_function_success(self):
        """Test executing a single function successfully."""
        executor = FunctionExecutor()

        # Mock the handler
        async def mock_handler(params, context):
            return {"ok": True, "test": "result"}

        executor._handlers["test_function"] = mock_handler

        # Register the function in registry
        with patch.object(executor.registry, "is_valid_function", return_value=True):
            with patch.object(executor.registry, "validate_call", return_value=(True, [])):
                result = await executor.execute_single(
                    function_name="test_function", parameters={"param1": "value1"}, context={"user_id": 123}
                )

        assert result.success is True
        assert result.function_name == "test_function"
        assert result.result == {"ok": True, "test": "result"}

    @pytest.mark.asyncio
    async def test_execute_all_with_multiple_functions(self):
        """Test executing multiple functions."""
        executor = FunctionExecutor()

        # Mock handlers
        async def success_handler(params, context):
            return {"ok": True}

        async def error_handler(params, context):
            raise ValueError("Test error")

        executor._handlers["success_func"] = success_handler
        executor._handlers["error_func"] = error_handler

        functions = [
            {"name": "success_func", "parameters": {}},
            {"name": "error_func", "parameters": {}},
        ]

        with patch.object(executor.registry, "is_valid_function", return_value=True):
            with patch.object(executor.registry, "validate_call", return_value=(True, [])):
                result = await executor.execute_all(functions, context={"user_id": 123})

        assert len(result.results) == 2
        assert result.results[0].success is True
        assert result.results[1].success is False
        assert result.all_succeeded is False

    @pytest.mark.asyncio
    async def test_extract_memory_handler(self):
        """Test the extract_memory function handler."""
        executor = FunctionExecutor()

        # Mock memory manager
        mock_memory_manager = Mock()
        mock_memory_manager.get_memory.return_value = []  # No existing memory
        mock_memory_manager.store_memory.return_value = None

        context = {"user_id": 123, "memory_manager": mock_memory_manager}

        params = {
            "key": "name",
            "value": "Sarah",
        }

        exec_result = await executor.execute_single("extract_memory", params, context)
        result = exec_result.result

        assert exec_result.success
        assert result["ok"] is True
        assert result["key"] == "name"
        assert result["value"] == "Sarah"
        assert result["updated"] is False  # New memory

        # Verify store_memory was called
        mock_memory_manager.store_memory.assert_called_once()
        call_args = mock_memory_manager.store_memory.call_args
        assert call_args[1]["key"] == "name"
        assert call_args[1]["value"] == "Sarah"


class TestResponseBuilder:
    """Test response building."""

    def test_build_response_with_successful_functions(self):
        """Test building response with successful function results."""
        builder = ResponseBuilder()

        execution_result = BatchExecutionResult(
            results=[
                ExecutionResult(
                    function_name="create_schedule", success=True, result={"time": "09:00", "schedule_id": 1}
                ),
                ExecutionResult(
                    function_name="extract_memory",
                    success=True,
                    result={"key": "preferred_lesson_time", "value": "09:00"},
                ),
            ],
            all_succeeded=True,
        )

        built = builder.build(
            user_text="Set my reminder for 9am",
            ai_response_text="I've set up your daily reminder.",
            execution_result=execution_result,
        )

        assert "I've set up your daily reminder." in built.text
        assert built.has_function_results is True
        assert len(built.successful_functions) == 2
        assert "create_schedule" in built.successful_functions
        assert "extract_memory" in built.successful_functions

    def test_build_response_with_failed_functions(self):
        """Test building response with failed function results."""
        builder = ResponseBuilder()

        execution_result = BatchExecutionResult(
            results=[ExecutionResult(function_name="create_schedule", success=False, error="Invalid time format")],
            all_succeeded=False,
        )

        built = builder.build(
            user_text="Set my reminder for invalid time",
            ai_response_text="I'll try to set that up.",
            execution_result=execution_result,
        )

        assert built.has_function_results is True
        assert len(built.failed_functions) == 1
        assert "create_schedule" in built.failed_functions

    def test_build_simple_response(self):
        """Test the simple response builder method."""
        builder = ResponseBuilder()

        text = builder.build_simple_response(ai_response_text="Hello there!", function_results=None)

        assert text == "Hello there!"


class TestIntegration:
    """Integration tests for the full flow."""

    def test_full_parse_and_validate_flow(self):
        """Test parsing a response and validating against registry."""
        # Get global instances
        registry = get_function_registry()
        parser = get_intent_parser()

        # Simulate an LLM response
        llm_response = json.dumps({
            "response": "I'll remember your name and set your timezone.",
            "functions": [
                {"name": "extract_memory", "parameters": {"key": "name", "value": "John"}},
                {"name": "set_timezone", "parameters": {"timezone": "Europe/Oslo"}},
            ],
        })

        # Parse the response
        parse_result = parser.parse(llm_response)

        assert parse_result.success is True
        assert len(parse_result.functions) == 2

        # Validate each function against registry
        for func in parse_result.functions:
            is_valid, errors = registry.validate_call(func["name"], func["parameters"])
            assert is_valid, f"Function {func['name']} validation failed: {errors}"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
