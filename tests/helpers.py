"""
DEPRECATED: Test helpers module.

This module is deprecated and will be removed in a future version.
All functionality has been moved to:

- tests/fixtures/     - Centralized fixtures
- tests/utils/        - Assertion helpers and builders  
- tests/mocks/        - Mock implementations

Migration Guide:
----------------
OLD: from tests.helpers import install_test_mocks
NEW: Fixtures are auto-imported via conftest.py

OLD: from tests.helpers import _patch_ollama_client
NEW: from tests.mocks.ollama_mock import patch_ollama_client

OLD: from tests.helpers import _patch_embedding_service
NEW: from tests.mocks.embedding_mock import patch_embedding_service

OLD: from tests.helpers import _register_fake_faiss
NEW: from tests.mocks.faiss_mock import register_fake_faiss

OLD: from tests.helpers import _patch_httpx_client
NEW: from tests.mocks.httpx_mock import patch_httpx_client

For new tests, please use the new structure in tests/fixtures/ and tests/utils/.
"""

import warnings

# Emit deprecation warning when this module is imported
warnings.warn(
    "tests.helpers is deprecated. Use tests.fixtures, tests.utils, and tests.mocks instead.",
    DeprecationWarning,
    stacklevel=2
)

# Re-export from new locations for backward compatibility
from tests.mocks.faiss_mock import _register_fake_faiss, register_fake_faiss
from tests.mocks.ollama_mock import create_mock_call_ollama, patch_ollama_client
from tests.mocks.embedding_mock import create_mock_embedding_service, patch_embedding_service
from tests.mocks.httpx_mock import patch_httpx_client, DummyResponse, DummyAsyncClient

# Legacy imports (kept for compatibility)
import os
import sys
import types
import importlib
from typing import Optional

import pytest


def _env_is_truthy(name: str) -> bool:
    """Return True for common truthy env values (1/true/yes/y)."""
    v = os.getenv(name)
    if not v:
        return False
    return str(v).strip().lower() in ("1", "true", "yes", "y")


def _get_embedding_dim() -> int:
    try:
        return int(os.getenv("EMBEDDING_DIMENSION", "384") or 384)
    except Exception:
        return 384


def _make_fake_call_ollama():
    async def _fake_call_ollama(prompt: str, model: Optional[str] = None, language: Optional[str] = None) -> str:
        short = (prompt[:160] + "...") if prompt and len(prompt) > 160 else (prompt or "")
        return f"[MOCK_OLLAMA_REPLY] model={model or 'default'} lang={language or 'en'} text={short}"

    return _fake_call_ollama


def _patch_ollama_client(monkeypatch):
    """DEPRECATED: Use tests.mocks.ollama_mock.patch_ollama_client instead."""
    warnings.warn(
        "_patch_ollama_client is deprecated. Use tests.mocks.ollama_mock.patch_ollama_client",
        DeprecationWarning,
        stacklevel=2
    )
    return patch_ollama_client(monkeypatch)


def _patch_ollama_online(monkeypatch):
    """DEPRECATED: No longer needed with new fixture system."""
    warnings.warn(
        "_patch_ollama_online is deprecated and no longer needed.",
        DeprecationWarning,
        stacklevel=2
    )
    try:
        _online = importlib.import_module("src.services.ollama_online_test")
        try:
            monkeypatch.setattr(_online, "run_ollama_checks", lambda *a, **k: (True, []))
        except Exception:
            pass
    except Exception:
        pass


def _patch_embedding_service(monkeypatch):
    """DEPRECATED: Use tests.mocks.embedding_mock.patch_embedding_service instead."""
    warnings.warn(
        "_patch_embedding_service is deprecated. Use tests.mocks.embedding_mock.patch_embedding_service",
        DeprecationWarning,
        stacklevel=2
    )
    return patch_embedding_service(monkeypatch)


def _patch_httpx_client(monkeypatch):
    """DEPRECATED: Use tests.mocks.httpx_mock.patch_httpx_client instead."""
    warnings.warn(
        "_patch_httpx_client is deprecated. Use tests.mocks.httpx_mock.patch_httpx_client",
        DeprecationWarning,
        stacklevel=2
    )
    return patch_httpx_client(monkeypatch)


@pytest.fixture(autouse=True)
def install_test_mocks(monkeypatch):
    """DEPRECATED: Mocks are now auto-installed via conftest.py.
    
    This fixture is kept for backward compatibility but does nothing
    as all mocks are now applied globally.
    """
    warnings.warn(
        "install_test_mocks fixture is deprecated. Mocks are auto-applied via conftest.py",
        DeprecationWarning,
        stacklevel=2
    )
    yield
