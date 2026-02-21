from __future__ import annotations

import os
import pytest


@pytest.fixture(autouse=True)
def mock_ollama_when_missing(monkeypatch):
    """Autouse fixture to stub out Ollama during tests when not requested.

    - If `TEST_USE_REAL_OLLAMA` or `USE_REAL_OLLAMA` is set, do nothing.
    - Otherwise monkeypatches `src.services.dialogue.ollama_client.call_ollama`
      with a simple async stub that returns a deterministic reply.
    """
    # Interpret common truthy values; treat unset or false-like values as False.
    def _env_is_truthy(name: str) -> bool:
        v = os.getenv(name)
        if not v:
            return False
        return str(v).strip().lower() in ("1", "true", "yes", "y")

    if _env_is_truthy("TEST_USE_REAL_OLLAMA") or _env_is_truthy("USE_REAL_OLLAMA"):
        return

    try:
        import importlib
        mod = importlib.import_module("src.services.dialogue.ollama_client")
    except Exception:
        return

    async def _fake_call_ollama(prompt: str, model: str | None = None, language: str | None = None) -> str:
        short = (prompt[:160] + "...") if prompt and len(prompt) > 160 else (prompt or "")
        return f"[MOCK_OLLAMA_REPLY] model={model or 'default'} lang={language or 'en'} text={short}"

    monkeypatch.setattr(mod, "call_ollama", _fake_call_ollama)
    yield
