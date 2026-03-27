"""HTTPX client mocking utilities."""

import os
from typing import Any, Dict
from unittest.mock import MagicMock


class DummyResponse:
    """Mock HTTPX response for testing."""

    def __init__(self, json_data: Dict | None = None, status_code: int = 200, text: str = ""):
        self.status_code = status_code
        self._text = text

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            import httpx

            raise httpx.HTTPStatusError("Mocked error", request=None, response=self)

    def json(self) -> Dict:
        return self._json

    @property
    def text(self) -> str:
        return self._text


class DummyAsyncClient:
    """Mock async HTTPX client for testing."""

    def __init__(self, response: DummyResponse | None = None, block_ollama: bool = True):
        self._response = response or DummyResponse()
        self._block_ollama = block_ollama

    async def __aenter__(self):
        return self

    async def __aexit__(self, exc_type, exc, tb):
        return False

    def _is_ollama_url(self, url: Any) -> bool:
        """Check if URL is an Ollama endpoint."""
        try:
            url_str = str(url)
        except Exception:
            return False

        local = os.getenv("LOCAL_OLLAMA_URL") or "http://localhost:11434"
        cloud = os.getenv("CLOUD_OLLAMA_URL") or "https://ollama.com"

        return local in url_str or cloud in url_str or "ollama.com" in url_str or "localhost:11434" in url_str

    async def post(self, *args, **kwargs) -> DummyResponse:
        """Mock POST request."""
        if self._block_ollama and args:
            url = args[0] if args else kwargs.get("url")
            if url and self._is_ollama_url(url):
                raise RuntimeError(f"Blocked outbound Ollama HTTP call during tests: {url}")
        return self._response

    async def get(self, *args, **kwargs) -> DummyResponse:
        """Mock GET request."""
        return self._response


def patch_httpx_client(monkeypatch, response: DummyResponse | None = None, block_ollama: bool = True) -> MagicMock:
    """Patch HTTPX AsyncClient.

    Usage:
        from tests.mocks.httpx_mock import patch_httpx_client, DummyResponse

        def test_something(monkeypatch):
            mock_response = DummyResponse(json_data={"result": "ok"})
            mock = patch_httpx_client(monkeypatch, response=mock_response)
            # ... test code
    """
    import httpx

    dummy_client = DummyAsyncClient(response=response, block_ollama=block_ollama)
    monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: dummy_client)

    return dummy_client


class HttpxMock:
    """Configurable HTTPX mock for tests.

    Usage:
        mock = HttpxMock()
        mock.set_response("https://api.example.com/data", json={"result": "ok"})

        with mock.patch():
            async with httpx.AsyncClient() as client:
                response = await client.get("https://api.example.com/data")
                assert response.json() == {"result": "ok"}
    """

    def __init__(self):
        self._responses: Dict[str, DummyResponse] = {}
        self._default_response = DummyResponse()
        self._block_ollama = True

    def set_response(
        self, url_pattern: str, json_data: Dict | None = None, status_code: int = 200, text: str = ""
    ) -> "HttpxMock":
        """Set a response for a URL pattern."""
        self._responses[url_pattern] = DummyResponse(json_data, status_code, text)
        return self

    def set_default_response(self, json_data: Dict | None = None, status_code: int = 200) -> "HttpxMock":
        """Set the default response."""
        self._default_response = DummyResponse(json_data, status_code)
        return self

    def allow_ollama(self) -> "HttpxMock":
        """Allow Ollama HTTP calls (disable blocking)."""
        self._block_ollama = False
        return self

    def _get_response(self, url: str) -> DummyResponse:
        """Get response for URL."""
        for pattern, response in self._responses.items():
            if pattern in url:
                return response
        return self._default_response

    def patch(self, monkeypatch):
        """Apply the mock using monkeypatch."""
        import httpx

        class ConfigurableDummyClient(DummyAsyncClient):
            def __init__(self, mock_instance: HttpxMock):
                self._mock = mock_instance

            async def post(self, *args, **kwargs):
                url = args[0] if args else kwargs.get("url", "")
                return self._mock._get_response(str(url))

            async def get(self, *args, **kwargs):
                url = args[0] if args else kwargs.get("url", "")
                return self._mock._get_response(str(url))

        monkeypatch.setattr(httpx, "AsyncClient", lambda **kwargs: ConfigurableDummyClient(self))

        return self
