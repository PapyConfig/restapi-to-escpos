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
    """Sends whole jobs to printers, one job at a time per printer.

    Closing matters: many printers send status bytes back (e.g. Automatic Status Back).
    Closing a socket with unread incoming bytes makes the kernel send a TCP RST instead of
    a FIN, and the printer then discards whatever it has not read yet: the end of a large
    image, the feed and the cut. So after sending, we half-close (FIN) and keep reading
    until the printer closes or `close_grace` expires. This lingering happens after the
    HTTP response, but the printer stays locked until it ends.
    """

    def __init__(self, timeout: float, close_grace: float = 5.0) -> None:
        self.timeout = timeout
        self.close_grace = close_grace
        self._locks: defaultdict[str, asyncio.Lock] = defaultdict(asyncio.Lock)
        self._lingering: set[asyncio.Task[None]] = set()

    async def send(self, printer: PrinterConfig, data: bytes) -> None:
        lock = self._locks[printer.name]
        await lock.acquire()
        writer: asyncio.StreamWriter | None = None
        try:
            async with asyncio.timeout(self.timeout):
                reader, writer = await asyncio.open_connection(printer.host, printer.port)
                writer.write(data)
                await writer.drain()
                if writer.can_write_eof():
                    writer.write_eof()
        except BaseException as exc:
            if writer is not None:
                writer.close()
            lock.release()
            if isinstance(exc, TimeoutError):
                raise PrinterTimeout(printer.name) from exc
            if isinstance(exc, OSError):
                raise PrinterUnreachable(printer.name) from exc
            raise
        task = asyncio.create_task(self._linger(reader, writer, lock))
        self._lingering.add(task)
        task.add_done_callback(self._lingering.discard)

    async def _linger(
        self, reader: asyncio.StreamReader, writer: asyncio.StreamWriter, lock: asyncio.Lock
    ) -> None:
        """Drain what the printer sends until it closes, then close gracefully."""
        try:
            with contextlib.suppress(TimeoutError, OSError):
                async with asyncio.timeout(self.close_grace):
                    while await reader.read(4096):
                        pass
            writer.close()
            with contextlib.suppress(OSError):
                await writer.wait_closed()
        finally:
            lock.release()

    async def aclose(self) -> None:
        """Wait for lingering connections (used at shutdown and in tests)."""
        if self._lingering:
            await asyncio.gather(*self._lingering, return_exceptions=True)

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
