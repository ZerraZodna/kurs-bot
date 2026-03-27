from __future__ import annotations

import json
import re
from typing import Set

from starlette.middleware.base import BaseHTTPMiddleware
from starlette.requests import Request
from starlette.responses import JSONResponse

from src.models.database import SessionLocal, User


class ConsentMiddleware(BaseHTTPMiddleware):
    """
    Enforce consent and processing restrictions for dialogue endpoints.

    This blocks requests for users who are deleted, restricted, or opted out.
    """

    def __init__(self, app, protected_prefix: str = "/api/v1/dialogue") -> None:
        super().__init__(app)
        self.protected_prefix = protected_prefix
        self.exempt_paths = {"/api/v1/dialogue/onboard"}
        self.exempt_prefixes = ("/api/v1/dialogue/lesson",)

    async def dispatch(self, request: Request, call_next):
        path = request.url.path
        if not path.startswith(self.protected_prefix):
            return await call_next(request)
        if path in self.exempt_paths or path.startswith(self.exempt_prefixes):
            return await call_next(request)

        user_ids = await _extract_user_ids(request)
        if not user_ids:
            return JSONResponse({"detail": "user_id required"}, status_code=400)

        db = SessionLocal()
        try:
            for user_id in user_ids:
                user = db.query(User).filter_by(user_id=user_id).first()
                if not user:
                    return JSONResponse({"detail": "User not found"}, status_code=404)
                if user.is_deleted:
                    return JSONResponse({"detail": "User deleted"}, status_code=410)
                if user.processing_restricted or not user.opted_in:
                    return JSONResponse({"detail": "Processing restricted"}, status_code=403)
        finally:
            db.close()

        return await call_next(request)


async def _extract_user_ids(request: Request) -> Set[int]:
    user_ids: Set[int] = set()

    path_user_id = _extract_user_id_from_path(request.url.path)
    if path_user_id is not None:
        user_ids.add(path_user_id)
        return user_ids

    body_bytes = await request.body()
    if body_bytes:
        try:
            payload = json.loads(body_bytes)
        except json.JSONDecodeError:
            payload = None

        if isinstance(payload, dict):
            _add_user_id(user_ids, payload.get("user_id"))
        elif isinstance(payload, list):
            for item in payload:
                if isinstance(item, dict):
                    _add_user_id(user_ids, item.get("user_id"))

    request._body = body_bytes
    return user_ids


def _extract_user_id_from_path(path: str) -> int | None:
    match = re.match(r"^/api/v1/dialogue/(?:context|memory)/(\d+)", path)
    if match:
        return int(match.group(1))
    return None


def _add_user_id(target: Set[int], value: object | None) -> None:
    if value is None:
        return
    try:
        target.add(int(value))
    except (TypeError, ValueError):
        return
