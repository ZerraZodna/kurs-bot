from __future__ import annotations


from fastapi import HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request

from src.config import settings


class ApiKeyAuthMiddleware(BaseHTTPMiddleware):
    """Optional API key auth for non-webhook endpoints."""

    def __init__(self, app, protected_prefix: str = "/api/v1") -> None:
        super().__init__(app)
        self.protected_prefix = protected_prefix
        self.exempt_paths = {"/", "/gdpr/privacy-notice"}
        self.exempt_prefixes = ("/webhook/",)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if path in self.exempt_paths or path.startswith(self.exempt_prefixes):
            return await call_next(request)

        if not path.startswith(self.protected_prefix):
            return await call_next(request)

        expected = settings.API_AUTH_TOKEN
        if not expected:
            return await call_next(request)

        token = _extract_token(request)
        if not token:
            raise HTTPException(status_code=401, detail="Missing API token")
        if token != expected:
            raise HTTPException(status_code=403, detail="Invalid API token")

        return await call_next(request)


def _extract_token(request: Request) -> str | None:
    auth = request.headers.get("Authorization")
    if auth and auth.startswith("Bearer "):
        return auth.split(" ", 1)[1].strip()
    x_api_key = request.headers.get("X-API-Key")
    if x_api_key:
        return x_api_key.strip()
    return None
