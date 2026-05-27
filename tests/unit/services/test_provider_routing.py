"""Tests for LLM provider routing in DialogueEngine."""

from unittest.mock import AsyncMock, MagicMock, patch

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
async def test_ollama_provider_routes_to_ollama(mock_session):
    """When LLM_PROVIDER=ollama, call_ollama routes to ollama_client."""
    with patch("src.services.dialogue_engine.settings") as mock_settings, \
         patch("src.services.dialogue_engine.get_user_timezone_from_db", return_value="Europe/Oslo"), \
         patch("src.services.dialogue_engine.MemoryManager") as mock_mm_cls, \
         patch("src.services.dialogue_engine.PromptBuilder") as mock_pb_cls, \
         patch("src.services.dialogue_engine.OnboardingService") as mock_os_cls, \
         patch("src.services.dialogue_engine.OnboardingFlow") as mock_of_cls:

        mock_settings.LLM_PROVIDER = "ollama"
        mock_settings.SYSTEM_PROMPT = "test prompt"

        mock_mm = MagicMock()
        mock_mm_cls.return_value = mock_mm

        mock_pb = MagicMock()
        mock_pb_cls.return_value = mock_pb

        mock_os = MagicMock()
        mock_os_cls.return_value = mock_os

        mock_of = MagicMock()
        mock_of.should_show_onboarding.return_value = False
        mock_of_cls.return_value = mock_of

        from src.services.dialogue_engine import DialogueEngine

        engine = DialogueEngine(db=mock_session)

        mock_ollama = AsyncMock(return_value="ollama response")
        with patch("src.services.dialogue.call_ollama", mock_ollama):
            result = await engine.call_ollama("test prompt")

        mock_ollama.assert_called_once_with("test prompt", None, None)
        assert result == "ollama response"


@pytest.mark.asyncio
async def test_openai_provider_routes_to_openai(mock_session):
    """When LLM_PROVIDER=openai, call_ollama routes to openai_client."""
    with patch("src.services.dialogue_engine.settings") as mock_settings, \
         patch("src.services.dialogue_engine.get_user_timezone_from_db", return_value="Europe/Oslo"), \
         patch("src.services.dialogue_engine.MemoryManager") as mock_mm_cls, \
         patch("src.services.dialogue_engine.PromptBuilder") as mock_pb_cls, \
         patch("src.services.dialogue_engine.OnboardingService") as mock_os_cls, \
         patch("src.services.dialogue_engine.OnboardingFlow") as mock_of_cls:

        mock_settings.LLM_PROVIDER = "openai"
        mock_settings.SYSTEM_PROMPT = "test prompt"

        mock_mm = MagicMock()
        mock_mm_cls.return_value = mock_mm

        mock_pb = MagicMock()
        mock_pb_cls.return_value = mock_pb

        mock_os = MagicMock()
        mock_os_cls.return_value = mock_os

        mock_of = MagicMock()
        mock_of.should_show_onboarding.return_value = False
        mock_of_cls.return_value = mock_of

        from src.services.dialogue_engine import DialogueEngine

        engine = DialogueEngine(db=mock_session)

        mock_openai = AsyncMock(return_value="openai response")
        with patch("src.services.dialogue.call_llm", mock_openai):
            result = await engine.call_ollama("test prompt")

        mock_openai.assert_called_once_with("test prompt", None, None)
        assert result == "openai response"
