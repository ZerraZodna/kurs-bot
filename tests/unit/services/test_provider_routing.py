"""Tests for LLM provider routing — single entry point call_llm_router."""

from unittest.mock import MagicMock, patch

import pytest


@pytest.fixture
def mock_session():
    """Create a mock DB session with a user."""
    session = MagicMock()
    user = MagicMock()
    user.user_id = 1
    user.is_deleted = False
    user.processing_restricted = False
    user.opted_in = True
    user.channel = "telegram"
    session.query.return_value.filter_by.return_value.first.return_value = user
    return session


@pytest.mark.asyncio
async def test_call_llm_router_uses_ollama(mock_session):
    """call_llm_router routes to ollama when LLM_PROVIDER=ollama."""
    with (
        patch("src.services.dialogue.settings") as mock_settings,
        patch("src.services.dialogue.call_ollama") as mock_ollama,
    ):
        mock_settings.LLM_PROVIDER = "ollama"
        mock_ollama.return_value = "ollama response"

        from src.services.dialogue import call_llm_router

        result = await call_llm_router("test prompt", model="qwen", language="en")

        mock_ollama.assert_called_once_with("test prompt", model="qwen", language="en", temperature=None)
        assert result == "ollama response"


@pytest.mark.asyncio
async def test_call_llm_router_uses_openai(mock_session):
    """call_llm_router routes to openai when LLM_PROVIDER=openai."""
    with (
        patch("src.services.dialogue.settings") as mock_settings,
        patch("src.services.dialogue.call_llm") as mock_openai,
    ):
        mock_settings.LLM_PROVIDER = "openai"
        mock_openai.return_value = "openai response"

        from src.services.dialogue import call_llm_router

        result = await call_llm_router("test prompt", model="gpt-4o", language="no")

        mock_openai.assert_called_once_with("test prompt", model="gpt-4o", language="no", temperature=None)
        assert result == "openai response"
