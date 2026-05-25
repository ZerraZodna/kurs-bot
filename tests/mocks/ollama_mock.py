"""Ollama client mocking utilities."""

import json
import os
import sys
import types
from unittest.mock import AsyncMock, MagicMock


def _env_is_truthy(name: str) -> bool:
    """Return True for common truthy env values (1/true/yes/y)."""
    v = os.getenv(name)
    if not v:
        return False
    return str(v).strip().lower() in ("1", "true", "yes", "y")


def create_fake_ollama_module() -> types.ModuleType:
    """Create a fake ollama module for import-time stubbing."""

    class _BlockedOllama(types.ModuleType):
        _allowed_attrs = {"__file__", "__spec__", "__path__", "__name__"}

        def __getattr__(self, attr):
            if attr in self._allowed_attrs:
                if attr == "__file__":
                    return "<blocked-ollama>"
                return None
            raise RuntimeError(
                "Access to the 'ollama' package is blocked in test runs (enable with TEST_USE_REAL_OLLAMA=1)."
            )

    fake_module = _BlockedOllama("ollama")
    try:
        fake_module.__file__ = "<blocked-ollama>"
    except Exception:
        pass

    return fake_module


def register_fake_ollama() -> None:
    """Register fake ollama module in sys.modules.

    Call this at import time to prevent real ollama initialization.
    """
    if "ollama" not in sys.modules and not _env_is_truthy("TEST_USE_REAL_OLLAMA"):
        sys.modules["ollama"] = create_fake_ollama_module()


def create_mock_call_ollama() -> AsyncMock:
    """Create a mock call_ollama function.

    Returns predictable responses for testing.
    """

    async def _mock_call_ollama(prompt: str, model: str | None = None, language: str | None = None) -> str:
        short = (prompt[:160] + "...") if prompt and len(prompt) > 160 else (prompt or "")
        return f"[MOCK_OLLAMA_REPLY] model={model or 'default'} lang={language or 'en'} text={short}"

    return AsyncMock(side_effect=_mock_call_ollama)


def patch_ollama_client(monkeypatch) -> MagicMock:
    """Patch the ollama client module.

    Usage:
        from tests.mocks.ollama_mock import patch_ollama_client

        def test_something(monkeypatch):
            mock = patch_ollama_client(monkeypatch)
            # ... test code
    """
    import src.services.dialogue.ollama_client as ollama_module

    mock_func = create_mock_call_ollama()
    monkeypatch.setattr(ollama_module, "call_ollama", mock_func)

    return mock_func


class OllamaMock:
    """Configurable Ollama mock for tests.

    Usage:
        mock = OllamaMock()
        mock.set_response("Hello", "Hi there!")
        mock.set_stream_calls("lesson", [{"name": "extract_memory", "arguments": '{"key":"current_lesson","value":"26"}'}])
        mock.set_stream_lesson_response("today", "Lesson 26 content here...")

        ollama_mock.patch(monkeypatch)
    """

    def __init__(self):
        self._responses: dict = {}
        self._stream_calls: dict = {}
        self._stream_lessons: dict = {}
        self._default_response = "[MOCK_OLLAMA_REPLY] Default response"

    def set_response(self, prompt_contains: str, response: str) -> "OllamaMock":
        """Set a response for prompts containing specific text."""
        self._responses[prompt_contains.lower()] = response
        return self

    def set_stream_calls(self, prompt_contains: str, tool_calls: list) -> "OllamaMock":
        """Set tool_calls for stream_ollama prompts containing specific text."""
        self._stream_calls[prompt_contains.lower()] = tool_calls
        return self

    def set_stream_lesson_response(self, prompt_contains: str, lesson_text: str) -> "OllamaMock":
        """Set direct lesson text stream for prompts containing specific text."""
        self._stream_lessons[prompt_contains.lower()] = lesson_text
        return self

    def set_default_response(self, response: str) -> "OllamaMock":
        """Set the default response for unmatched prompts."""
        self._default_response = response
        return self

    async def _mock_call(self, prompt: str, model: str | None = None, language: str | None = None) -> str:
        prompt_lower = prompt.lower()

        for key, response in self._responses.items():
            if key in prompt_lower:
                return response

        return self._default_response

    async def _mock_stream(self, prompt: str, model: str | None = None, language: str | None = None):
        """Mock stream_ollama yielding Ollama JSON chunks: lesson text, tool_calls, or default."""
        prompt_lower = prompt.lower()

        # 1. Check for lesson text first (direct LLM response simulation)
        for key, lesson_text in self._stream_lessons.items():
            if key in prompt_lower:
                # Yield lesson text as Ollama response tokens
                for word in lesson_text.split():
                    chunk = json.dumps({"response": word, "done": False})
                    yield chunk
                yield json.dumps({"done": True})
                return

        # 2. Check for tool_calls
        tool_calls = None
        for key, calls in self._stream_calls.items():
            if key in prompt_lower:
                tool_calls = calls
                break

        if tool_calls:
            # Yield JSON with functions for intent_parser + lesson content
            full_json = json.dumps({"Forgivenessfunctions": tool_calls})
            yield full_json
            yield json.dumps({"done": True})
            return

        # 3. Default text stream
        chunks = [json.dumps({"response": "OK", "done": False}), json.dumps({"done": True})]
        for chunk in chunks:
            yield chunk

    def patch(self, monkeypatch):
        """Apply the mock using monkeypatch."""
        import src.services.dialogue.ollama_client as ollama_module

        monkeypatch.setattr(ollama_module, "call_ollama", self._mock_call)
        monkeypatch.setattr(ollama_module, "stream_ollama", self._mock_stream)
        return self
