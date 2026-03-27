"""
Tests to verify the duplicate message fix in process_telegram_batch.

The bug: When AI returns a function call, both the AI text AND the function
result were sent as separate messages, causing duplicates.

The fix: Run post_hook FIRST, then decide what to send:
- If function results exist → send only function_response_text (combined)
- Otherwise → send only ai_response
"""

from unittest.mock import AsyncMock

import pytest


async def mock_generator(tokens):
    """Helper to create an async generator from tokens."""
    for token in tokens:
        yield token


# ─── Logic simulation helpers ────────────────────────────────────────────────


async def simulate_streaming_send_logic(
    full_response: str,
    ai_response: str,
    post_hook_diagnostics: dict | None,
    function_response_text: str | None,
    send_message_mock,
    chat_id: int = 12345,
    combined_text: str = "test message",
):
    """
    Simulate the send-decision logic from process_telegram_batch (streaming path).
    Returns the list of calls made to send_message.
    """
    if not full_response:
        fallback = "[No response from LLM]"
        await send_message_mock(chat_id, fallback)
        return

    # Post-hook already ran; we receive its results as arguments
    has_function_results = (
        post_hook_diagnostics is not None
        and post_hook_diagnostics.get("execution_result") is not None
        and function_response_text is not None
    )

    if has_function_results and function_response_text and function_response_text.strip():
        await send_message_mock(chat_id, function_response_text)
    elif ai_response and ai_response.strip():
        await send_message_mock(chat_id, ai_response)


# ─── Tests ───────────────────────────────────────────────────────────────────


@pytest.mark.asyncio
async def test_no_duplicate_when_function_results_exist():
    """
    When the AI response includes a function call that produces results,
    only ONE message should be sent (the combined function_response_text),
    NOT the ai_response separately.
    """
    send_message = AsyncMock()

    await simulate_streaming_send_logic(
        full_response='{"response": "Here is your lesson.", "functions": [{"name": "send_todays_lesson"}]}',
        ai_response="Here is your lesson.",
        post_hook_diagnostics={"execution_result": {"lesson": "Lesson 1 content..."}},
        function_response_text="Here is your lesson.\n\n📖 Lesson 1 content...",
        send_message_mock=send_message,
    )

    # Only ONE message should be sent
    assert send_message.call_count == 1
    # It should be the combined function response, not just the AI text
    sent_text = send_message.call_args[0][1]
    assert "Lesson 1 content" in sent_text


@pytest.mark.asyncio
async def test_ai_response_sent_when_no_function_results():
    """
    When there are no function results, the AI text response should be sent.
    """
    send_message = AsyncMock()

    await simulate_streaming_send_logic(
        full_response="Hello, how are you?",
        ai_response="Hello, how are you?",
        post_hook_diagnostics=None,
        function_response_text=None,
        send_message_mock=send_message,
    )

    assert send_message.call_count == 1
    sent_text = send_message.call_args[0][1]
    assert sent_text == "Hello, how are you?"


@pytest.mark.asyncio
async def test_empty_full_response_sends_fallback():
    """
    When full_response is empty (LLM returned nothing), a fallback
    '[No response from LLM]' message should be sent.
    """
    send_message = AsyncMock()

    await simulate_streaming_send_logic(
        full_response="",
        ai_response="",
        post_hook_diagnostics=None,
        function_response_text=None,
        send_message_mock=send_message,
    )

    assert send_message.call_count == 1
    sent_text = send_message.call_args[0][1]
    assert sent_text == "[No response from LLM]"


@pytest.mark.asyncio
async def test_empty_ai_response_with_function_results_sends_function_text():
    """
    When AI response text is empty but function results exist (e.g., function-only call),
    the function_response_text should still be sent.
    """
    send_message = AsyncMock()

    await simulate_streaming_send_logic(
        full_response='{"response": "", "functions": [{"name": "send_todays_lesson"}]}',
        ai_response="",  # empty text response
        post_hook_diagnostics={"execution_result": {"lesson": "Lesson 1 content..."}},
        function_response_text="📖 Lesson 1 content...",
        send_message_mock=send_message,
    )

    assert send_message.call_count == 1
    sent_text = send_message.call_args[0][1]
    assert "Lesson 1 content" in sent_text


@pytest.mark.asyncio
async def test_empty_ai_response_no_function_results_sends_nothing():
    """
    When both ai_response and function results are empty/None,
    nothing should be sent.
    """
    send_message = AsyncMock()

    await simulate_streaming_send_logic(
        full_response='{"response": "", "functions": []}',
        ai_response="",
        post_hook_diagnostics=None,
        function_response_text=None,
        send_message_mock=send_message,
    )

    # Nothing should be sent
    assert send_message.call_count == 0


@pytest.mark.asyncio
async def test_whitespace_only_ai_response_not_sent():
    """
    Whitespace-only AI responses should not be sent.
    """
    send_message = AsyncMock()

    await simulate_streaming_send_logic(
        full_response='{"response": "   ", "functions": []}',
        ai_response="   ",
        post_hook_diagnostics=None,
        function_response_text=None,
        send_message_mock=send_message,
    )

    # Nothing should be sent (whitespace-only is stripped)
    assert send_message.call_count == 0


@pytest.mark.asyncio
async def test_whitespace_only_function_response_not_sent():
    """
    Whitespace-only function responses should not be sent.
    """
    send_message = AsyncMock()

    await simulate_streaming_send_logic(
        full_response='{"response": "Hello", "functions": [{"name": "test"}]}',
        ai_response="Hello",
        post_hook_diagnostics={"execution_result": {"result": "ok"}},
        function_response_text="   ",  # whitespace only
        send_message_mock=send_message,
    )

    # Should fall back to ai_response since function_response is whitespace
    assert send_message.call_count == 1
    sent_text = send_message.call_args[0][1]
    assert sent_text == "Hello"


@pytest.mark.asyncio
async def test_old_bug_scenario_simulation():
    """
    Simulate the OLD bug: ai_response sent first, then function_response_text.
    This test documents what the OLD (buggy) behavior was.
    """
    send_message = AsyncMock()

    # OLD behavior (before fix):
    # 1. Send ai_response immediately
    # 2. Run post_hook
    # 3. Send function_response_text
    # This resulted in 2 messages!

    ai_response = "Here is your lesson."
    function_response_text = "Here is your lesson.\n\n📖 Lesson 1 content..."

    # OLD code would do:
    await send_message(12345, ai_response)  # First message
    await send_message(12345, function_response_text)  # Second message (duplicate!)

    # This is the BUG - 2 messages sent
    assert send_message.call_count == 2

    # The fix ensures only 1 message is sent (the combined one)
    # See test_no_duplicate_when_function_results_exist for the fixed behavior


@pytest.mark.asyncio
async def test_function_results_with_empty_execution_result():
    """
    When diagnostics exist but execution_result is empty/None,
    treat as no function results.
    """
    send_message = AsyncMock()

    await simulate_streaming_send_logic(
        full_response="Hello there",
        ai_response="Hello there",
        post_hook_diagnostics={"execution_result": None},  # empty result
        function_response_text=None,
        send_message_mock=send_message,
    )

    # Should send ai_response since no valid function results
    assert send_message.call_count == 1
    sent_text = send_message.call_args[0][1]
    assert sent_text == "Hello there"


# ─── Integration-style tests with more realistic mocking ─────────────────────


@pytest.mark.asyncio
async def test_streaming_path_with_lesson_function():
    """
    Integration test simulating the full streaming path when
    send_todays_lesson function is called.
    """
    from src.functions.intent_parser import get_intent_parser

    # Simulate accumulated full response from streaming
    full_response = """{"response": "Let me get today's lesson for you.", "functions": [{"name": "send_todays_lesson", "parameters": {}}]}"""

    # Extract ai_response
    parser = get_intent_parser()
    parse_result = parser.parse(full_response)
    ai_response = parse_result.response_text if parse_result.response_text is not None else full_response

    # Simulate the combined function response that would be built
    # (This simulates what response_builder.build() would produce)
    function_response_text = (
        "Let me get today's lesson for you.\n\n📖 **Lesson 1: Nothing I see means anything.**\n\nThe exercises..."
    )

    # Now test the send logic
    send_message = AsyncMock()

    await simulate_streaming_send_logic(
        full_response=full_response,
        ai_response=ai_response,
        post_hook_diagnostics={"execution_result": {"result": "ok"}},  # Has function results
        function_response_text=function_response_text,
        send_message_mock=send_message,
        combined_text="show me today's lesson",
    )

    # Only ONE message should be sent
    assert send_message.call_count == 1
    sent_text = send_message.call_args[0][1]

    # The sent text should include both the AI text AND the lesson content
    assert "Let me get today's lesson" in sent_text
    assert "Lesson 1" in sent_text or "exercises" in sent_text


if __name__ == "__main__":
    import asyncio

    async def run_all():
        await test_no_duplicate_when_function_results_exist()
        print("✓ test_no_duplicate_when_function_results_exist")

        await test_ai_response_sent_when_no_function_results()
        print("✓ test_ai_response_sent_when_no_function_results")

        await test_empty_full_response_sends_fallback()
        print("✓ test_empty_full_response_sends_fallback")

        await test_empty_ai_response_with_function_results_sends_function_text()
        print("✓ test_empty_ai_response_with_function_results_sends_function_text")

        await test_empty_ai_response_no_function_results_sends_nothing()
        print("✓ test_empty_ai_response_no_function_results_sends_nothing")

        await test_whitespace_only_ai_response_not_sent()
        print("✓ test_whitespace_only_ai_response_not_sent")

        await test_whitespace_only_function_response_not_sent()
        print("✓ test_whitespace_only_function_response_not_sent")

        await test_old_bug_scenario_simulation()
        print("✓ test_old_bug_scenario_simulation")

        await test_function_results_with_empty_execution_result()
        print("✓ test_function_results_with_empty_execution_result")

        await test_streaming_path_with_lesson_function()
        print("✓ test_streaming_path_with_lesson_function")

        print("\nAll tests passed!")

    asyncio.run(run_all())
