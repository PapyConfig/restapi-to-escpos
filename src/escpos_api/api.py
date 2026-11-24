"""HTTP routes."""

from __future__ import annotations

import asyncio
import logging
import time
import uuid
from typing import Annotated

from fastapi import APIRouter, Depends, File, Form, Request, Response, UploadFile
from starlette.concurrency import run_in_threadpool

from . import __version__
from .config import PrinterConfig, Settings
from .errors import ApiError
from .imaging import ImageLimits
from .models import (
    Align,
    ErrorResponse,
    ImageMode,
    ImageOptions,
    PrinterInfo,
    PrintJob,
    PrintResult,
)
from .renderer import render_image, render_job
from .security import require_api_key
from .transport import Transport

log = logging.getLogger("escpos_api")

_ERRORS = {code: {"model": ErrorResponse} for code in (401, 404, 413, 422, 502, 504)}

public = APIRouter()
v1 = APIRouter(prefix="/v1", dependencies=[Depends(require_api_key)], responses=_ERRORS)


def _settings(request: Request) -> Settings:
    return request.app.state.settings


def _transport(request: Request) -> Transport:
    return request.app.state.transport


SettingsDep = Annotated[Settings, Depends(_settings)]
TransportDep = Annotated[Transport, Depends(_transport)]


def _limits(settings: Settings) -> ImageLimits:
    return ImageLimits(
        max_bytes=settings.max_image_bytes,
        max_pixels=settings.max_image_pixels,
        max_height=settings.max_image_height,
    )


def _printer(settings: Settings, name: str | None) -> PrinterConfig:
    name = name or settings.default_printer
    printer = settings.printers_by_name.get(name or "")
    if printer is None:
        raise ApiError(404, "unknown_printer", f"Printer {name!r} is not declared.")
    return printer


async def _deliver(
    transport: Transport,
    printer: PrinterConfig,
    data: bytes,
    started: float,
    kind: str,
    count: int,
) -> PrintResult:
    job_id = str(uuid.uuid4())
    try:
        await transport.send(printer, data)
    except ApiError as exc:
        log.warning("job=%s printer=%s kind=%s result=%s", job_id, printer.name, kind, exc.error)
        raise
    duration = int((time.perf_counter() - started) * 1000)
    log.info(
        "job=%s printer=%s kind=%s commands=%d bytes=%d duration_ms=%d result=ok",
        job_id,
        printer.name,
        kind,
        count,
        len(data),
        duration,
    )
    return PrintResult(job_id=job_id, printer=printer.name, bytes=len(data), duration_ms=duration)


@public.get("/health", tags=["service"])
async def health() -> dict[str, str]:
    return {"status": "ok", "version": __version__}


@v1.get("/printers", response_model=list[PrinterInfo], tags=["printers"])
async def list_printers(settings: SettingsDep, transport: TransportDep) -> list[PrinterInfo]:
    reachable = await asyncio.gather(*(transport.probe(p) for p in settings.printers))
    return [
        PrinterInfo(**p.model_dump(), default=p.name == settings.default_printer, reachable=ok)
        for p, ok in zip(settings.printers, reachable, strict=True)
    ]


@v1.post("/print", response_model=PrintResult, tags=["print"])
async def print_job(job: PrintJob, settings: SettingsDep, transport: TransportDep) -> PrintResult:
    """Render the whole job, then send it to the printer in one block."""
    started = time.perf_counter()
    printer = _printer(settings, job.printer)
    data = await run_in_threadpool(render_job, job, printer, _limits(settings))
    return await _deliver(transport, printer, data, started, "job", len(job.commands))


@v1.post("/print/image", response_model=PrintResult, tags=["print"])
async def print_image(
    settings: SettingsDep,
    transport: TransportDep,
    file: Annotated[UploadFile, File(description="PNG, JPEG, GIF, BMP or WebP")],
    printer: Annotated[str | None, Form()] = None,
    align: Annotated[Align, Form()] = "center",
    mode: Annotated[ImageMode, Form()] = "dither",
    threshold: Annotated[int, Form(ge=0, le=255)] = 128,
    width: Annotated[int | None, Form(ge=8, le=2048)] = None,
    upscale: Annotated[bool, Form()] = False,
    cut: Annotated[bool, Form()] = True,
) -> PrintResult:
    """Print a single uploaded image, scaled to the paper width."""
    started = time.perf_counter()
    target = _printer(settings, printer)
    data = await file.read(settings.max_image_bytes + 1)
    opts = ImageOptions(align=align, mode=mode, threshold=threshold, width=width, upscale=upscale)
    stream = await run_in_threadpool(render_image, data, opts, cut, target, _limits(settings))
    return await _deliver(transport, target, stream, started, "image", 1)


@v1.post(
    "/render",
    tags=["print"],
    response_class=Response,
    responses={200: {"content": {"application/octet-stream": {}}}},
)
async def render(job: PrintJob, settings: SettingsDep) -> Response:
    """Return the ESC/POS stream of a job without printing it."""
    printer = _printer(settings, job.printer)
    data = await run_in_threadpool(render_job, job, printer, _limits(settings))
    return Response(
        data, media_type="application/octet-stream", headers={"X-Escpos-Bytes": str(len(data))}
    )
