"""
Test for lesson response when AI generates introductory text.

This test verifies that when the AI generates introductory text but calls
send_todays_lesson, the final response includes the full lesson content
from the function result, not just the AI's introductory text.
"""

from src.functions.response_builder import ResponseBuilder
from src.functions.executor import ExecutionResult, BatchExecutionResult


def test_lesson_response_prioritizes_function_content_over_ai_text():
    """
    Test that when AI generates text like "Today's lesson from A Course in Miracles is:"
    but also calls send_todays_lesson, the final response includes the full lesson content.
    
    This simulates the bug where the AI was generating introductory text instead of
    leaving the response field empty.
    """
    builder = ResponseBuilder()
    
    # Simulate AI generating introductory text (the bug behavior)
    ai_response_text = "Today's lesson from A Course in Miracles is:"
    
    # But the function was called and returned full content
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
        user_text="what is today's lesson?",
        ai_response_text=ai_response_text,
        execution_result=batch_result,
        include_function_results=True
    )
    
    # Print for debugging
    print("\n=== Built Response ===")
    print(built.text)
    print("======================\n")
    
    # The response should include the full lesson content
    assert "Lesson 20" in built.text
    assert "I am determined to see." in built.text
    assert "The idea for today is a beginning step" in built.text
    assert "truly helpful thing" in built.text
    
    # The AI's introductory text should be present but the lesson content should dominate
    assert built.has_function_results is True
    assert "send_todays_lesson" in built.successful_functions


def test_lesson_response_with_empty_ai_text():
    """
    Test the ideal case where AI leaves response field empty.
    This is what we want the AI to do after the prompt fix.
    """
    builder = ResponseBuilder()
    
    # AI leaves response empty (ideal behavior)
    ai_response_text = ""
    
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
    
    built = builder.build(
        user_text="what is today's lesson?",
        ai_response_text=ai_response_text,
        execution_result=batch_result,
        include_function_results=True
    )
    
    print("\n=== Built Response (Empty AI Text) ===")
    print(built.text)
    print("======================================\n")
    
    # Should only have the lesson content, no extra text
    assert built.text.startswith("📖 <strong>Lesson 20</strong>")
    assert "I am determined to see." in built.text
    assert "The idea for today is a beginning step" in built.text


def test_lesson_content_not_truncated():
    """
    Test that the full lesson content is included and not truncated.
    """
    builder = ResponseBuilder()
    
    # Full lesson content (simulating a real ACIM lesson)
    full_content = """1. The idea for today is a beginning step in bringing thoughts together and teaching you that what you are studying is a unified thought system in which nothing is lacking that is needed, and nothing is included that is contradictory or confusing.

2. The truly helpful thing in this way of seeing is that you recognize the problem and the answer are not separate. This is the beginning of true vision.

3. You will begin to understand what you are learning when you have realized that you do not understand it. This is the beginning of true vision."""
    
    lesson_result = ExecutionResult(
        function_name="send_todays_lesson",
        success=True,
        result={
            "lesson_id": 20,
            "title": "I am determined to see.",
            "content": full_content
        },
        execution_time_ms=50.0
    )
    
    batch_result = BatchExecutionResult(
        results=[lesson_result],
        all_succeeded=True,
        total_execution_time_ms=50.0
    )
    
    built = builder.build(
        user_text="give me the entire lesson",
        ai_response_text="",
        execution_result=batch_result,
        include_function_results=True
    )
    
    print("\n=== Full Lesson Content Test ===")
    print(f"Content length: {len(built.text)}")
    print("================================\n")
    
    # All paragraphs should be present
    assert "1. The idea for today" in built.text
    assert "2. The truly helpful thing" in built.text
    assert "3. You will begin to understand" in built.text
    assert len(built.text) > len(full_content)  # Should include title and formatting


if __name__ == "__main__":
    test_lesson_response_prioritizes_function_content_over_ai_text()
    test_lesson_response_with_empty_ai_text()
    test_lesson_content_not_truncated()
    print("All tests passed!")
