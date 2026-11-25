"""Application factory and ASGI entry point (`escpos_api.main:app`)."""

from __future__ import annotations

import logging
from urllib.parse import urlsplit

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from starlette.types import ASGIApp, Message, Receive, Scope, Send

from . import __version__
from .api import public, v1
from .config import Settings
from .errors import ApiError
from .transport import Transport
from .ui import mount_ui

log = logging.getLogger("escpos_api")


class BodyLimitMiddleware:
    """Reject request bodies larger than `limit` bytes with 413."""

    def __init__(self, app: ASGIApp, limit: int) -> None:
        self.app = app
        self.limit = limit

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        headers = dict(scope.get("headers") or [])
        declared = headers.get(b"content-length")
        if declared is not None and declared.isdigit() and int(declared) > self.limit:
            await self._reject(scope, receive, send)
            return

        received = 0
        rejected = False

        async def limited_receive() -> Message:
            nonlocal received, rejected
            message = await receive()
            if message["type"] == "http.request" and not rejected:
                received += len(message.get("body", b""))
                if received > self.limit:
                    rejected = True
                    await self._reject(scope, receive, send)
                    return {"type": "http.disconnect"}
            return message

        async def guarded_send(message: Message) -> None:
            if not rejected:
                await send(message)

        await self.app(scope, limited_receive, guarded_send)

    async def _reject(self, scope: Scope, receive: Receive, send: Send) -> None:
        error = ApiError(413, "payload_too_large", f"Request body exceeds {self.limit} bytes.")
        await JSONResponse(error.body(), status_code=413)(scope, receive, send)


_UNSAFE_METHODS = frozenset({"POST", "PUT", "PATCH", "DELETE"})


class OriginCheckMiddleware:
    """Refuse browser write requests coming from a foreign origin (CSRF).

    A reverse proxy may inject the API key for authenticated SSO users, so a third-party page
    must not be able to make the browser submit a print job. Browsers always send `Origin` on
    cross-origin POSTs; clients without `Origin` (curl, n8n) are unaffected. The scheme is not
    compared because TLS is usually terminated by the proxy.
    """

    def __init__(self, app: ASGIApp, allowed_origins: list[str]) -> None:
        self.app = app
        self.allowed = {o.rstrip("/").lower() for o in allowed_origins}

    def _allowed(self, origin: str, host: str) -> bool:
        origin = origin.rstrip("/").lower()
        if origin in self.allowed:
            return True
        parts = urlsplit(origin)
        return parts.scheme in ("http", "https") and bool(host) and parts.netloc == host

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] == "http" and scope["method"] in _UNSAFE_METHODS:
            headers = dict(scope.get("headers") or [])
            origin = headers.get(b"origin")
            if origin is not None:
                host = headers.get(b"host", b"").decode("latin-1").lower()
                if not self._allowed(origin.decode("latin-1"), host):
                    log.warning("refused cross-origin %s %s", scope["method"], scope["path"])
                    error = ApiError(403, "forbidden_origin", "Cross-origin request refused.")
                    await JSONResponse(error.body(), status_code=403)(scope, receive, send)
                    return
        await self.app(scope, receive, send)


def create_app(settings: Settings | None = None) -> FastAPI:
    settings = settings or Settings()
    logging.basicConfig(
        level=settings.log_level.upper(),
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
        force=True,  # python-escpos may have configured the root logger on import
    )

    app = FastAPI(
        title="ESC/POS Print API",
        version=__version__,
        description=(
            "Render JSON print jobs and images to ESC/POS network printers. "
            "All `/v1` routes require the `X-API-Key` header."
        ),
    )
    app.state.settings = settings
    app.state.transport = Transport(settings.printer_timeout)

    @app.exception_handler(ApiError)
    async def _api_error(_: Request, exc: ApiError) -> JSONResponse:
        return JSONResponse(exc.body(), status_code=exc.status)

    @app.exception_handler(RequestValidationError)
    async def _validation_error(_: Request, exc: RequestValidationError) -> JSONResponse:
        details = [{"loc": list(e["loc"]), "reason": e["msg"]} for e in exc.errors()]
        error = ApiError(422, "invalid_job", "The request is invalid.", details)
        return JSONResponse(error.body(), status_code=422)

    @app.exception_handler(Exception)
    async def _unexpected(_: Request, exc: Exception) -> JSONResponse:
        log.exception("unexpected error")
        error = ApiError(500, "internal_error", "Internal error, see server logs.")
        return JSONResponse(error.body(), status_code=500)

    app.include_router(public)
    app.include_router(v1)
    if settings.ui_enabled:
        mount_ui(app)

    if settings.cors_origins:
        app.add_middleware(
            CORSMiddleware,
            allow_origins=settings.cors_origins,
            allow_methods=["GET", "POST"],
            allow_headers=["Content-Type", "X-API-Key"],
        )
    app.add_middleware(OriginCheckMiddleware, allowed_origins=settings.cors_origins)
    app.add_middleware(BodyLimitMiddleware, limit=settings.max_request_bytes)

    log.info(
        "ESC/POS Print API %s - printers: %s (default: %s)%s",
        __version__,
        ", ".join(f"{p.name}={p.host}:{p.port}" for p in settings.printers),
        settings.default_printer,
        "" if settings.api_key else " - WARNING: authentication disabled",
    )
    if settings.ui_enabled:
        log.info("Web UI enabled on /ui/")
    return app
