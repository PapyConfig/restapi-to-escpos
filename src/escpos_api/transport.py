"""Asynchronous raw-TCP delivery of a rendered ESC/POS stream."""

from __future__ import annotations

import asyncio
import contextlib
from collections import defaultdict

from .config import PrinterConfig
from .errors import ApiError


class PrinterUnreachable(ApiError):
    def __init__(self, printer: str) -> None:
        super().__init__(502, "printer_unreachable", f"Printer {printer!r} is unreachable.")


class PrinterTimeout(ApiError):
    def __init__(self, printer: str) -> None:
        super().__init__(504, "printer_timeout", f"Printer {printer!r} did not respond in time.")


class Transport:
    """Sends whole jobs to printers, one job at a time per printer."""

    def __init__(self, timeout: float) -> None:
        self.timeout = timeout
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)

    async def send(self, printer: PrinterConfig, data: bytes) -> None:
        async with self._locks[printer.name]:
            writer: asyncio.StreamWriter | None = None
            try:
                async with asyncio.timeout(self.timeout):
                    _, writer = await asyncio.open_connection(printer.host, printer.port)
                    writer.write(data)
                    await writer.drain()
                    writer.close()
                    await writer.wait_closed()
            except TimeoutError as exc:
                raise PrinterTimeout(printer.name) from exc
            except OSError as exc:
                raise PrinterUnreachable(printer.name) from exc
            finally:
                if writer is not None and not writer.is_closing():
                    writer.close()

    async def probe(self, printer: PrinterConfig, within: float = 2.0) -> bool:
        """True when a TCP connection to the printer can be opened."""
        try:
            async with asyncio.timeout(within):
                _, writer = await asyncio.open_connection(printer.host, printer.port)
        except (OSError, TimeoutError):
            return False
        writer.close()
        with contextlib.suppress(OSError):
            await writer.wait_closed()
        return True
