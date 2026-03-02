"""
Test for lesson text response building.

This test verifies that when send_todays_lesson function is called,
the response builder correctly formats the full lesson content.
"""

import pytest
from src.functions.response_builder import ResponseBuilder, BuiltResponse
from src.functions.executor import ExecutionResult, BatchExecutionResult


def test_send_todays_lesson_includes_full_content():
    """Test that send_todays_lesson response includes full lesson content."""
    builder = ResponseBuilder()
    
    # Simulate the result from send_todays_lesson function
    lesson_result = ExecutionResult(
        function_name="send_todays_lesson",
        success=True,
        result={
            "lesson_id": 20,
            "title": "I am determined to see.",
            "content": "1. The idea for today is a beginning step in bringing thoughts together and teaching you that what you are studying is a unified thought system in which nothing is lacking that is needed, and nothing is included that is contradictory or confusing.\n\n2. The truly helpful thing in this way of seeing is that you recognize the problem and the answer are not separate. This is the beginning of true vision."
        },
        execution_time_ms=50.0
    )
    
    batch_result = BatchExecutionResult(
        results=[lesson_result],
        all_succeeded=True,
        total_execution_time_ms=50.0
    )
    
    # Build the response
    built = builder.build(
        user_text="give me the text of todays lesson",
        ai_response_text="Here is today's lesson:",
        execution_result=batch_result,
        include_function_results=True
    )
    
    # Verify the response includes the full content
    assert "Lesson 20" in built.text
    assert "I am determined to see." in built.text
    assert "The idea for today is a beginning step" in built.text
    assert "truly helpful thing" in built.text
    
    # Print for debugging
    print("\n=== Built Response ===")
    print(built.text)
    print("======================\n")
    
    # Verify it has function results
    assert built.has_function_results is True
    assert "send_todays_lesson" in built.successful_functions


def test_send_lesson_with_content():
    """Test that send_lesson response includes full content."""
    builder = ResponseBuilder()
    
    lesson_result = ExecutionResult(
        function_name="send_lesson",
        success=True,
        result={
            "lesson_id": 15,
            "title": "My thoughts are images that I have made.",
            "content": "1. Whatever you see reflects your thoughts. It is your thoughts that tell you where you are and what your reality is.\n\n2. You are the source of all your experiences."
        },
        execution_time_ms=45.0
    )
    
    batch_result = BatchExecutionResult(
        results=[lesson_result],
        all_succeeded=True,
        total_execution_time_ms=45.0
    )
    
    built = builder.build(
        user_text="show me lesson 15",
        ai_response_text="",
        execution_result=batch_result,
        include_function_results=True
    )
    
    # Verify content is included
    assert "Lesson 15" in built.text
    assert "My thoughts are images" in built.text
    assert "Whatever you see reflects your thoughts" in built.text
    
    print("\n=== Built Response for Lesson 15 ===")
    print(built.text)
    print("====================================\n")


def test_template_formatting():
    """Test that templates are correctly formatted with content."""
    builder = ResponseBuilder()
    
    # Test the template directly
    template = builder.success_templates["send_todays_lesson"]
    
    # Format with sample data
    formatted = template.format(
        lesson_id=20,
        title="I am determined to see.",
        content="Full lesson text here..."
    )
    
    print("\n=== Formatted Template ===")
    print(formatted)
    print("==========================\n")
    
    assert "Lesson 20" in formatted
    assert "I am determined to see." in formatted
    assert "Full lesson text here..." in formatted


if __name__ == "__main__":
    test_send_todays_lesson_includes_full_content()
    test_send_lesson_with_content()
    test_template_formatting()
    print("All tests passed!")
