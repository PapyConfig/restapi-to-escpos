"""API key authentication."""

from __future__ import annotations

import secrets

from fastapi import Request, Security
from fastapi.security import APIKeyHeader

from .errors import ApiError

_header = APIKeyHeader(name="X-API-Key", auto_error=False)


async def require_api_key(request: Request, key: str | None = Security(_header)) -> None:
    settings = request.app.state.settings
    if not settings.api_key:
        return  # ALLOW_NO_AUTH=true, checked at startup
    if not key or not secrets.compare_digest(key.encode(), settings.api_key.encode()):
        raise ApiError(401, "unauthorized", "Missing or invalid API key (X-API-Key header).")
