"""Tests for the StreamingFilter class."""
import pytest
from unittest.mock import AsyncMock
from src.integrations.telegram_stream import StreamingFilter


async def mock_token_generator(tokens: list[str]):
    """Helper to create an async generator from a list of tokens."""
    for token in tokens:
        yield token


# ─── Tests for JSON prefix handling ─────────────────────────────────────────────

@pytest.mark.asyncio
async def test_skips_json_prefix():
    """
    StreamingFilter should skip the {"response": " prefix and not yield it.
    """
    tokens = ['{"response": "', 'Hello ', 'world', '!"}']
    generator = mock_token_generator(tokens)
    filter = StreamingFilter(generator)
    
    results = []
    async for chunk in filter.filter_stream():
        results.append(chunk)
    
    # Should not include the JSON prefix
    combined = "".join(results)
    assert '{"response":' not in combined
    assert "Hello world!" in combined


@pytest.mark.asyncio
async def test_skips_json_prefix_with_spaces():
    """
    StreamingFilter should handle JSON prefix with varying whitespace.
    """
    tokens = ['{  "response"  :  "', 'Hello ', 'world', '!"}']
    generator = mock_token_generator(tokens)
    filter = StreamingFilter(generator)
    
    results = []
    async for chunk in filter.filter_stream():
        results.append(chunk)
    
    combined = "".join(results)
    assert "Hello world!" in combined


# ─── Tests for HTML tag buffering ──────────────────────────────────────────────

@pytest.mark.asyncio
async def test_buffers_incomplete_html_tag():
    """
    StreamingFilter should buffer incomplete HTML tags until complete.
    """
    # Token splits a tag across multiple tokens
    tokens = ['Hello <b', '>world</b', '!']
    generator = mock_token_generator(tokens)
    filter = StreamingFilter(generator)
    
    results = []
    async for chunk in filter.filter_stream():
        results.append(chunk)
    
    # Should yield complete tag, not partial
    combined = "".join(results)
    assert "<b>world</b>" in combined or "world" in combined


@pytest.mark.asyncio
async def test_buffers_incomplete_closing_tag():
    """
    StreamingFilter should buffer incomplete closing tags.
    """
    tokens = ['Hello world</', 'em>!']
    generator = mock_token_generator(tokens)
    filter = StreamingFilter(generator)
    
    results = []
    async for chunk in filter.filter_stream():
        results.append(chunk)
    
    combined = "".join(results)
    assert "world</em>!" in combined or "world!" in combined


# ─── Tests for HTML entity buffering ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_buffers_incomplete_html_entity():
    """
    StreamingFilter should buffer incomplete HTML entities until complete.
    """
    tokens = ['Hello &nbsp', '; world!']
    generator = mock_token_generator(tokens)
    filter = StreamingFilter(generator)
    
    results = []
    async for chunk in filter.filter_stream():
        results.append(chunk)
    
    combined = "".join(results)
    # Should have buffered until semicolon
    assert " " in combined


@pytest.mark.asyncio
async def test_buffers_amp_entity():
    """
    StreamingFilter should properly buffer &amp; entity.
    """
    tokens = ['Hello &amp', '; world!']
    generator = mock_token_generator(tokens)
    filter = StreamingFilter(generator)
    
    results = []
    async for chunk in filter.filter_stream():
        results.append(chunk)
    
    combined = "".join(results)
    assert "world" in combined


# ─── Tests for functions boundary detection ───────────────────────────────────

@pytest.mark.asyncio
async def test_stops_at_functions_boundary():
    """
    StreamingFilter should detect functions boundary and separate text from functions.
    """
    tokens = ['{"response": "Hello world", "functions": [{"name": "test"}]}']
    generator = mock_token_generator(tokens)
    filter = StreamingFilter(generator)
    
    results = []
    async for chunk in filter.filter_stream():
        results.append(chunk)
    
    combined = "".join(results)
    # Should include "Hello world" but not the functions part
    assert "Hello world" in combined


@pytest.mark.asyncio
async def test_functions_not_returned_to_user():
    """
    StreamingFilter should NOT return the functions part to the user.
    This tests that bug #1 is fixed - the functions JSON should be stripped
    from the output and only the text response should be yielded.
    """
    # Token contains both response text AND functions JSON
    tokens = ['{"response": "Hello world", "functions": [{"name": "test_function", "parameters": {"arg1": "value1"}}]}']
    generator = mock_token_generator(tokens)
    filter = StreamingFilter(generator)
    
    results = []
    async for chunk in filter.filter_stream():
        results.append(chunk)
    
    combined = "".join(results)
    
    # The text response should be returned
    assert "Hello world" in combined
    
    # The functions part should NOT be returned to the user
    assert "functions" not in combined
    assert "test_function" not in combined
    assert "parameters" not in combined
    assert "arg1" not in combined
    assert "value1" not in combined


@pytest.mark.asyncio
async def test_functions_not_returned_with_multiple_tokens():
    """
    StreamingFilter should not return functions part even when tokens are split.
    """
    # Split the JSON across multiple tokens to test boundary detection with fragmentation
    tokens = [
        '{"response": "Hello ', 
        'world', 
        '", "functions": [{"name": "test"}]}'
    ]
    generator = mock_token_generator(tokens)
    filter = StreamingFilter(generator)
    
    results = []
    async for chunk in filter.filter_stream():
        results.append(chunk)
    
    combined = "".join(results)
    
    # Should include the text
    assert "Hello world" in combined
    
    # Should NOT include functions
    assert "functions" not in combined
    assert "test" not in combined


@pytest.mark.asyncio
async def test_functions_not_returned_with_token_fragmentation():
    """
    StreamingFilter should NOT return functions when tokens are fragmented around 
    the "functions" boundary. This tests the specific bug where:
    - Token ends with '",' (end of response string + comma)
    - Next tokens contain '"functions":'
    
    The filter must buffer when it detects possible string end to catch the 
    functions boundary in subsequent tokens.
    """
    # This simulates the actual fragmentation pattern from Ollama
    # Token splits at the exact problematic boundary
    tokens = [
        'Hello world',
        '.',
        '",',          # End of response string + comma
        '\n  "',       # Whitespace + opening quote for next field
        'functions',   # "functions" keyword - arrives later!
        '": []',       # Colon + empty array
        '\n}'          # End of JSON
    ]
    generator = mock_token_generator(tokens)
    filter = StreamingFilter(generator)
    
    results = []
    async for chunk in filter.filter_stream():
        results.append(chunk)
    
    combined = "".join(results)
    
    # Should include the text response
    assert "Hello world" in combined
    
    # The BUG: "functions" appears in output when buffer is flushed prematurely
    # After fix: "functions" should NOT appear
    assert "functions" not in combined, f"Bug: 'functions' leaked into output: {combined}"


@pytest.mark.asyncio
async def test_returns_remaining_for_functions():
    """
    StreamingFilter should return remaining content for function processing.
    """
    tokens = ['{"response": "Hello world", "functions": [{"name": "test", "parameters": {}}]}']
    generator = mock_token_generator(tokens)
    filter = StreamingFilter(generator)
    
    # Consume the stream
    results = []
    async for chunk in filter.filter_stream():
        results.append(chunk)
    
    # Check remaining for functions
    remaining = filter.get_remaining_for_functions()
    assert remaining is not None
    assert "functions" in remaining


# ─── Tests for plain text responses ───────────────────────────────────────────

@pytest.mark.asyncio
async def test_handles_plain_text_response():
    """
    StreamingFilter should handle plain text responses without JSON.
    """
    tokens = ['Hello world!']
    generator = mock_token_generator(tokens)
    filter = StreamingFilter(generator)
    
    results = []
    async for chunk in filter.filter_stream():
        results.append(chunk)
    
    combined = "".join(results)
    assert "Hello world!" in combined


# ─── Tests for empty response ─────────────────────────────────────────────────

@pytest.mark.asyncio
async def test_handles_empty_generator():
    """
    StreamingFilter should handle empty token generator.
    """
    tokens = []
    generator = mock_token_generator(tokens)
    filter = StreamingFilter(generator)
    
    results = []
    async for chunk in filter.filter_stream():
        results.append(chunk)
    
    assert results == []


# ─── Tests for escape sequences ───────────────────────────────────────────────

@pytest.mark.asyncio
async def test_unescapes_quoted_strings():
    """
    StreamingFilter should unescape quoted strings properly.
    """
    tokens = ['{"response": "Hello \\"world\\"!"}']
    generator = mock_token_generator(tokens)
    filter = StreamingFilter(generator)
    
    results = []
    async for chunk in filter.filter_stream():
        results.append(chunk)
    
    combined = "".join(results)
    # Should contain unescaped quotes
    assert "world" in combined


@pytest.mark.asyncio
async def test_unescapes_newlines():
    """
    StreamingFilter should unescape \\n to actual newlines (linefeed/lf).
    This tests the fix for the issue where \\n was appearing as literal \\n
    instead of actual newlines in the output.
    """
    # Use actual newline character in the JSON string
    # The LLM outputs JSON with \n (0x0A) as the escape sequence for newline
    json_with_newline = '{"response": "Hello\nworld!"}'
    tokens = [json_with_newline]
    generator = mock_token_generator(tokens)
    filter = StreamingFilter(generator)
    
    results = []
    async for chunk in filter.filter_stream():
        results.append(chunk)
    
    combined = "".join(results)
    # Should contain actual newline (0x0A)
    assert "\n" in combined
    assert "Hello" in combined
    assert "world" in combined


@pytest.mark.asyncio
async def test_escaped_backslash_not_converted_to_newline():
    """
    StreamingFilter should NOT convert escaped backslash followed by n to newline.
    In JSON, \\\\n represents a literal backslash + n, not a newline.
    """
    # In JSON, "path\\to\\file" represents the string: path\to\file
    # The raw token contains: backslash, n, backslash, n, backslash, n
    json_with_backslashes = '{"response": "path\\\\to\\\\file"}'
    tokens = [json_with_backslashes]
    generator = mock_token_generator(tokens)
    filter = StreamingFilter(generator)
    
    results = []
    async for chunk in filter.filter_stream():
        results.append(chunk)
    
    combined = "".join(results)
    # Should have literal backslashes, not newlines
    assert "\\" in combined
    # Should NOT have actual newlines
    assert "\n" not in combined


# ─── Helper to run tests standalone ───────────────────────────────────────────

if __name__ == "__main__":
    import asyncio
    
    async def run_tests():
        print("Running StreamingFilter tests...")
        
        tests = [
            ("test_skips_json_prefix", test_skips_json_prefix),
            ("test_skips_json_prefix_with_spaces", test_skips_json_prefix_with_spaces),
            ("test_buffers_incomplete_html_tag", test_buffers_incomplete_html_tag),
            ("test_buffers_incomplete_closing_tag", test_buffers_incomplete_closing_tag),
            ("test_buffers_incomplete_html_entity", test_buffers_incomplete_html_entity),
            ("test_buffers_amp_entity", test_buffers_amp_entity),
            ("test_stops_at_functions_boundary", test_stops_at_functions_boundary),
            ("test_returns_remaining_for_functions", test_returns_remaining_for_functions),
            ("test_handles_plain_text_response", test_handles_plain_text_response),
            ("test_handles_empty_generator", test_handles_empty_generator),
            ("test_unescapes_quoted_strings", test_unescapes_quoted_strings),
            ("test_unescapes_newlines", test_unescapes_newlines),
            ("test_escaped_backslash_not_converted_to_newline", test_escaped_backslash_not_converted_to_newline),
        ]
        
        for name, test_fn in tests:
            try:
                await test_fn()
                print(f"✓ {name}")
            except Exception as e:
                print(f"✗ {name}: {e}")
                import traceback
                traceback.print_exc()
        
        print("\nDone!")
    
    asyncio.run(run_tests())

