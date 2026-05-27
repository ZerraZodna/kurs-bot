"""Unit tests for the OpenAI-compatible LLM client."""

import importlib
from unittest.mock import AsyncMock, MagicMock, patch

import pytest


@pytest.fixture
def mock_settings():
    """Patch settings at the source (src.config) so reload picks up patched values."""
    with patch("src.config.settings") as mock:
        mock.OPENAI_MODEL = "gpt-4o"
        mock.OPENAI_BASE_URL = "http://test.local/v1"
        mock.OPENAI_API_KEY = "sk-test"
        mock.OPENAI_TEMPERATURE = 0.2
        mock.OPENAI_TIMEOUT = 120.0
        mock.OPENAI_LONG_TIMEOUT = 380.0
        mock.NON_ENGLISH_OLLAMA_MODEL = "gpt-oss:20b"
        mock.IS_TEST_ENV = False
        mock.TEST_USE_REAL_OLLAMA = False
        yield mock


@pytest.fixture
def mock_openai_response():
    """Create a mock OpenAI chat completion response."""
    response = MagicMock()
    response.choices = [MagicMock(message=MagicMock(content="Hello, how can I help you?"))]
    return response


class TestCallLlm:
    """Tests for the non-streaming call_llm function.

    Note: conftest globally monkeypatches call_llm with a mock. These tests
    need the real implementation so that the AsyncOpenAI mock actually runs.
    We reload the module to bypass the monkeypatch.  The mock_settings fixture
    patches src.config.settings (the source), so the reload picks up the
    patched config values.
    """

    def _real_module(self):
        """Reload openai_client to get the real call_llm, bypassing conftest monkeypatch."""
        import src.services.dialogue.openai_client as oc

        importlib.reload(oc)
        return oc

    @pytest.mark.asyncio
    async def test_returns_content_from_response(self, mock_settings, mock_openai_response):
        """call_llm returns the content from the first choice."""
        oc = self._real_module()
        with patch.object(oc, "AsyncOpenAI") as mock_async_openai:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
            mock_async_openai.return_value = mock_client

            result = await oc.call_llm("Hello")

            assert result == "Hello, how can I help you?"
            mock_client.chat.completions.create.assert_called_once()
            call_args = mock_client.chat.completions.create.call_args
            assert call_args[1]["model"] == "gpt-4o"
            assert call_args[1]["messages"] == [{"role": "user", "content": "Hello"}]

    @pytest.mark.asyncio
    async def test_uses_custom_model(self, mock_settings, mock_openai_response):
        """call_llm uses the provided model parameter."""
        oc = self._real_module()
        with patch.object(oc, "AsyncOpenAI") as mock_async_openai:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
            mock_async_openai.return_value = mock_client

            await oc.call_llm("Hello", model="gpt-3.5-turbo")

            call_args = mock_client.chat.completions.create.call_args
            assert call_args[1]["model"] == "gpt-3.5-turbo"

    @pytest.mark.asyncio
    async def test_uses_custom_temperature(self, mock_settings, mock_openai_response):
        """call_llm passes the temperature parameter."""
        oc = self._real_module()
        with patch.object(oc, "AsyncOpenAI") as mock_async_openai:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
            mock_async_openai.return_value = mock_client

            await oc.call_llm("Hello", temperature=0.7)

            call_args = mock_client.chat.completions.create.call_args
            assert call_args[1]["temperature"] == 0.7

    @pytest.mark.asyncio
    async def test_handles_empty_response(self, mock_settings):
        """call_llm returns error message when response has no choices."""
        oc = self._real_module()
        with patch.object(oc, "AsyncOpenAI") as mock_async_openai:
            mock_client = AsyncMock()
            mock_response = MagicMock()
            mock_response.choices = []
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_async_openai.return_value = mock_client

            result = await oc.call_llm("Hello")

            assert result == "[No response from LLM]"

    @pytest.mark.asyncio
    async def test_handles_api_error(self, mock_settings):
        """call_llm returns error message on exception."""
        oc = self._real_module()
        with patch.object(oc, "AsyncOpenAI") as mock_async_openai:
            mock_async_openai.side_effect = Exception("Connection refused")

            result = await oc.call_llm("Hello")

            assert result == "[Sorry, I couldn't process your request right now.]"

    @pytest.mark.asyncio
    async def test_uses_base_url_and_api_key(self, mock_settings, mock_openai_response):
        """call_llm passes base_url and api_key to AsyncOpenAI."""
        oc = self._real_module()
        with patch.object(oc, "AsyncOpenAI") as mock_async_openai:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_openai_response)
            mock_async_openai.return_value = mock_client

            await oc.call_llm("Hello")

            mock_async_openai.assert_called_once()
            call_kwargs = mock_async_openai.call_args[1]
            assert call_kwargs["base_url"] == "http://test.local/v1"
            assert call_kwargs["api_key"] == "sk-test"


class TestStreamLlm:
    """Tests for the streaming stream_llm function."""

    @pytest.mark.asyncio
    async def test_yields_content_chunks(self, mock_settings):
        """stream_llm yields content from each chunk."""
        mock_chunk1 = MagicMock()
        mock_chunk1.choices = [MagicMock(delta=MagicMock(content="Hello"))]
        mock_chunk1.choices[0].finish_reason = None

        mock_chunk2 = MagicMock()
        mock_chunk2.choices = [MagicMock(delta=MagicMock(content=" world"))]
        mock_chunk2.choices[0].finish_reason = "stop"

        async def make_async_iter():
            for chunk in [mock_chunk1, mock_chunk2]:
                yield chunk

        mock_response = make_async_iter()

        with patch("src.services.dialogue.openai_client.AsyncOpenAI") as mock_async_openai:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_async_openai.return_value = mock_client

            from src.services.dialogue.openai_client import stream_llm

            tokens = []
            async for token in stream_llm("Hello"):
                tokens.append(token)

            assert tokens == ["Hello", " world"]

    @pytest.mark.asyncio
    async def test_handles_empty_chunks(self, mock_settings):
        """stream_llm skips chunks with no content."""
        mock_chunk1 = MagicMock()
        mock_chunk1.choices = [MagicMock(delta=MagicMock(content=None))]
        mock_chunk1.choices[0].finish_reason = "stop"

        async def make_async_iter():
            yield mock_chunk1

        mock_response = make_async_iter()

        with patch("src.services.dialogue.openai_client.AsyncOpenAI") as mock_async_openai:
            mock_client = AsyncMock()
            mock_client.chat.completions.create = AsyncMock(return_value=mock_response)
            mock_async_openai.return_value = mock_client

            from src.services.dialogue.openai_client import stream_llm

            tokens = []
            async for token in stream_llm("Hello"):
                tokens.append(token)

            assert tokens == []

    @pytest.mark.asyncio
    async def test_fallback_on_error(self, mock_settings, mock_openai_response):
        """stream_llm falls back to call_llm on exception."""
        with (
            patch("src.services.dialogue.openai_client.AsyncOpenAI") as mock_async_openai,
            patch("src.services.dialogue.openai_client.call_llm", new_callable=AsyncMock) as mock_call,
        ):
            mock_async_openai.side_effect = Exception("Network error")
            mock_call.return_value = "fallback response"

            from src.services.dialogue.openai_client import stream_llm

            tokens = []
            async for token in stream_llm("Hello"):
                tokens.append(token)

            assert tokens == ["fallback response"]


class TestConfigDefaults:
    """Tests for default configuration values."""

    def test_openai_timeout_default(self, mock_settings):
        from src.services.dialogue.openai_client import OPENAI_TIMEOUT

        assert OPENAI_TIMEOUT == 120.0

    def test_openai_long_timeout_default(self, mock_settings):
        from src.services.dialogue.openai_client import OPENAI_LONG_TIMEOUT

        assert OPENAI_LONG_TIMEOUT == 380.0

    def test_openai_temperature_default(self, mock_settings):
        from src.services.dialogue.openai_client import OPENAI_TEMPERATURE

        assert OPENAI_TEMPERATURE == 0.2

    def test_is_long_model(self, mock_settings):
        from src.services.dialogue.openai_client import _is_long_model

        assert _is_long_model("gpt-oss:120b") is True
        assert _is_long_model("gpt-oss:20b") is True
        assert _is_long_model("gpt-4o") is False
        assert _is_long_model("qwen3:latest") is False
        assert _is_long_model(None) is False
