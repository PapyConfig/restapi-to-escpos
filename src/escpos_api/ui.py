"""Optional static web UI (`UI_ENABLED=true`), served on `/ui/`."""

from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI
from fastapi.responses import RedirectResponse
from starlette.responses import Response
from starlette.staticfiles import StaticFiles
from starlette.types import Scope

UI_DIR = Path(__file__).parent / "ui"

CSP = "; ".join(
    [
        "default-src 'none'",
        "script-src 'self'",
        "style-src 'self'",
        "img-src 'self' data: blob:",
        "connect-src 'self'",
        "manifest-src 'self'",
        "base-uri 'none'",
        "form-action 'none'",
        "frame-ancestors 'none'",
    ]
)

SECURITY_HEADERS = {
    "Content-Security-Policy": CSP,
    "X-Content-Type-Options": "nosniff",
    "Referrer-Policy": "no-referrer",
    "Cache-Control": "no-cache",
}


class SecureStaticFiles(StaticFiles):
    """StaticFiles adding a strict CSP and no-cache to every response."""

    async def get_response(self, path: str, scope: Scope) -> Response:
        response = await super().get_response(path, scope)
        response.headers.update(SECURITY_HEADERS)
        return response


def mount_ui(app: FastAPI) -> None:
    async def to_ui() -> RedirectResponse:
        return RedirectResponse("/ui/", status_code=307)

    app.add_api_route("/", to_ui, include_in_schema=False)
    app.add_api_route("/ui", to_ui, include_in_schema=False)
    app.mount("/ui", SecureStaticFiles(directory=UI_DIR, html=True), name="ui")
