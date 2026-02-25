"""Ollama client mocking utilities."""

import os
import sys
import types
from typing import Optional
from unittest.mock import MagicMock, AsyncMock


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
    async def _mock_call_ollama(
        prompt: str,
        model: Optional[str] = None,
        language: Optional[str] = None
    ) -> str:
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
        
        with mock.patch():
            result = await call_ollama("Hello")
            assert result == "Hi there!"
    """
    
    def __init__(self):
        self._responses: dict = {}
        self._default_response = "[MOCK_OLLAMA_REPLY] Default response"
    
    def set_response(self, prompt_contains: str, response: str) -> "OllamaMock":
        """Set a response for prompts containing specific text."""
        self._responses[prompt_contains.lower()] = response
        return self
    
    def set_default_response(self, response: str) -> "OllamaMock":
        """Set the default response for unmatched prompts."""
        self._default_response = response
        return self
    
    async def _mock_call(
        self,
        prompt: str,
        model: Optional[str] = None,
        language: Optional[str] = None
    ) -> str:
        prompt_lower = prompt.lower()
        
        for key, response in self._responses.items():
            if key in prompt_lower:
                return response
        
        return self._default_response
    
    def patch(self, monkeypatch):
        """Apply the mock using monkeypatch."""
        import src.services.dialogue.ollama_client as ollama_module
        monkeypatch.setattr(ollama_module, "call_ollama", self._mock_call)
        return self
