from __future__ import annotations

import asyncio
import io
import socket
from collections.abc import AsyncIterator

import httpx
import pytest
from PIL import Image

from escpos_api.config import PrinterConfig, Settings
from escpos_api.imaging import ImageLimits
from escpos_api.main import create_app

API_KEY = "test-key"
HEADERS = {"X-API-Key": API_KEY}


class FakePrinter:
    """TCP server recording every connection's payload."""

    def __init__(self, delay: float = 0.0) -> None:
        self.jobs: list[bytes] = []
        self.connections = 0
        self.active = 0
        self.max_active = 0
        self.delay = delay
        self.server: asyncio.Server | None = None
        self.port = 0

    async def _handle(self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter) -> None:
        self.connections += 1
        self.active += 1
        self.max_active = max(self.max_active, self.active)
        chunks = []
        while data := await reader.read(65536):
            chunks.append(data)
            if self.delay:
                await asyncio.sleep(self.delay)
        self.jobs.append(b"".join(chunks))
        self.active -= 1
        writer.close()

    async def start(self) -> None:
        self.server = await asyncio.start_server(self._handle, "127.0.0.1", 0)
        self.port = self.server.sockets[0].getsockname()[1]

    async def stop(self) -> None:
        assert self.server
        self.server.close()
        await self.server.wait_closed()


def free_port() -> int:
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        return s.getsockname()[1]


def make_settings(port: int, **overrides) -> Settings:
    values = {
        "api_key": API_KEY,
        "printers": [
            PrinterConfig(name="main", host="127.0.0.1", port=port),
            PrinterConfig(name="small", host="127.0.0.1", port=port, width=384),
        ],
        "printer_timeout": 2,
    }
    values.update(overrides)
    return Settings(_env_file=None, **values)


@pytest.fixture
async def printer() -> AsyncIterator[FakePrinter]:
    fake = FakePrinter()
    await fake.start()
    yield fake
    await fake.stop()


async def wait_jobs(printer: FakePrinter, count: int) -> None:
    for _ in range(100):
        if len(printer.jobs) >= count:
            return
        await asyncio.sleep(0.01)


@pytest.fixture
async def client(printer: FakePrinter) -> AsyncIterator[httpx.AsyncClient]:
    app = create_app(make_settings(printer.port))
    transport = httpx.ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest.fixture
def limits() -> ImageLimits:
    return ImageLimits(max_bytes=10 * 1024 * 1024, max_pixels=25_000_000, max_height=4000)


@pytest.fixture
def main_printer() -> PrinterConfig:
    return PrinterConfig(name="main", host="127.0.0.1", port=9100)


def png_bytes(size=(100, 50), mode="RGB", color=(0, 0, 0), fmt="PNG") -> bytes:
    buf = io.BytesIO()
    Image.new(mode, size, color).save(buf, fmt)
    return buf.getvalue()
